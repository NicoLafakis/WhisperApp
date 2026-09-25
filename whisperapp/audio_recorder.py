import ctypes
import logging
import os
import shutil
import threading
import time
import uuid
import wave
from array import array
from pathlib import Path
from tempfile import gettempdir
from typing import Callable, List, Optional

import pyaudio

from whisperapp.dictation_store import DictationStore


logger = logging.getLogger(__name__)


# Hard ceiling on a single take. A stuck push-to-talk once ran for ~83 minutes and
# produced a 160 MB WAV that could never be uploaded. Ten minutes at the recorder's own
# format (16 kHz mono 16-bit) is 19.2 MB, comfortably inside OpenAI's 25 MB limit.
MAX_RECORDING_SECONDS = 600.0

# How many finished takes stay on disk. Recordings are the user's own files now that
# they live in Documents rather than %TEMP%, so the old ten was needlessly stingy:
# twenty-five covers "yesterday's dictation came out wrong, find me that take" and still
# caps the folder well under the size a single stuck recording used to reach.
MAX_RETAINED_RECORDINGS = 25

# How long to wait for the capture thread to notice the stop flag and exit.
_THREAD_JOIN_TIMEOUT_SECONDS = 1.5

# Where takes are kept, relative to the user's Documents folder.
_RECORDINGS_SUBPATH = ("WhisperApp", "recordings")

# FOLDERID_Documents. Passed to SHGetKnownFolderPath, which is the only call that
# reports where Documents *currently* is: OneDrive's "back up your folders" redirects it
# out from under the profile, so Path.home() / "Documents" silently writes to a stale
# folder the user never looks at.
# https://learn.microsoft.com/en-us/windows/win32/api/shlobj_core/nf-shlobj_core-shgetknownfolderpath
_FOLDERID_DOCUMENTS = "{FDD39AD0-238F-46AF-ADB4-6C85480369C7}"


def _documents_dir_via_known_folder() -> Optional[Path]:
    """Resolve Documents through the shell's known-folder API. ``None`` if unavailable."""
    if os.name != "nt":
        return None

    try:
        from ctypes import wintypes

        class _GUID(ctypes.Structure):
            _fields_ = [
                ("Data1", wintypes.DWORD),
                ("Data2", wintypes.WORD),
                ("Data3", wintypes.WORD),
                ("Data4", ctypes.c_ubyte * 8),
            ]

        guid = _GUID()
        # Parsing the canonical GUID text beats spelling its byte order out by hand.
        if ctypes.windll.ole32.CLSIDFromString(
            ctypes.c_wchar_p(_FOLDERID_DOCUMENTS), ctypes.byref(guid)
        ) != 0:
            return None

        buffer = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(
            ctypes.byref(guid), 0, None, ctypes.byref(buffer)
        ) != 0:
            return None
        try:
            return Path(buffer.value) if buffer.value else None
        finally:
            # The shell allocated that string; leaking it every launch is still a leak.
            ctypes.windll.ole32.CoTaskMemFree(buffer)
    except Exception:
        logger.debug("SHGetKnownFolderPath lookup failed", exc_info=True)
        return None


def _documents_dir_via_registry() -> Optional[Path]:
    """Fall back to the shell-folders registry value, which records the same redirect."""
    if os.name != "nt":
        return None

    try:
        import winreg

        key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, "Personal")
        # The value is REG_EXPAND_SZ - it usually still contains %USERPROFILE%.
        expanded = os.path.expandvars(str(value)).strip()
        return Path(expanded) if expanded else None
    except Exception:
        logger.debug("User Shell Folders lookup failed", exc_info=True)
        return None


def _documents_dir() -> Optional[Path]:
    """The user's Documents folder, honouring OneDrive/known-folder redirection."""
    for resolve in (_documents_dir_via_known_folder, _documents_dir_via_registry):
        documents = resolve()
        if documents is not None:
            return documents
    return None


def _resolve_recordings_dir() -> Path:
    """Where takes should be written. Never raises; the directory may not exist yet."""
    documents = _documents_dir()
    if documents is None:
        # Non-Windows, or a machine that answered neither lookup. The home-relative
        # guess is wrong under a redirect, which is exactly why it is the last resort.
        documents = Path.home() / "Documents"
    return documents.joinpath(*_RECORDINGS_SUBPATH)


def _legacy_recordings_dir() -> Path:
    """Where takes lived before they moved to Documents.

    Still the log directory (see ``main.LOG_DIR``), so it is emptied of recordings only.
    """
    return Path(gettempdir()) / "whisperapp"


def _prepare_recordings_dir() -> Path:
    """Create the recordings directory, falling back to the old temp one if we cannot."""
    directory = _resolve_recordings_dir()
    try:
        directory.mkdir(parents=True, exist_ok=True)
        return directory
    except OSError:
        # A Documents folder that cannot be written to - locked-down profile, or a
        # OneDrive redirect pointing somewhere currently offline - must not cost the
        # user the ability to record at all.
        logger.warning(
            "Could not create %s; falling back to the temp directory", directory, exc_info=True
        )

    directory = _legacy_recordings_dir()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _migrate_legacy_recordings(destination: Path) -> None:
    """Move takes left behind in %TEMP%\\whisperapp into *destination*, once.

    Best effort throughout: a take that cannot be moved stays where it is and the app
    still starts, and a name collision is always resolved in favour of the file already
    at the destination rather than by overwriting it.
    """
    source = _legacy_recordings_dir()
    if source == destination or not source.is_dir():
        return

    for old in source.glob("recording_*.wav"):
        target = destination / old.name
        if target.exists():
            continue
        try:
            # move() keeps the modification time, which the retention prune sorts on.
            shutil.move(str(old), str(target))
        except OSError:
            logger.warning("Could not move %s to %s", old, target, exc_info=True)

    # Migrate journals and text as well, including text whose completed WAV was
    # already pruned. Also finishes a move interrupted after moving only the WAV.
    for pattern in ("recording_*.txt", "recording_*.json"):
        for old in source.glob(pattern):
            target = destination / old.name
            if old.with_suffix(".wav").exists() or target.exists():
                # A WAV still at the source means its move failed or collided. Keep
                # its companions together rather than attach them to different audio.
                continue
            try:
                shutil.move(str(old), target)
            except OSError:
                logger.warning("Could not migrate recording companion %s", old, exc_info=True)

    try:
        if not any(source.iterdir()):
            source.rmdir()
    except OSError:
        # Usually just the log file still sitting there. Nothing to do about it.
        logger.debug("Leaving %s in place", source, exc_info=True)


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        audio_device: Optional[str] = None,
        max_duration_seconds: float = MAX_RECORDING_SECONDS,
        on_max_duration_reached: Optional[Callable[[Optional[Path]], None]] = None,
        on_capture_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.audio_format = pyaudio.paInt16
        self.audio_device = audio_device
        self.max_duration_seconds = max_duration_seconds
        self.on_max_duration_reached = on_max_duration_reached
        self.on_capture_error = on_capture_error

        self._pyaudio = pyaudio.PyAudio()
        self._stream = None
        self._frames: List[bytes] = []
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._level_lock = threading.Lock()
        self._volume_level = 0.0
        self._hit_duration_limit = False
        self._finalized_path: Optional[Path] = None
        self._wav_writer = None
        self._wav_file = None

        self.recordings_dir = _prepare_recordings_dir()
        self.output_path: Optional[Path] = None

        # Before any pruning, so takes rescued out of %TEMP% are counted as kept files
        # rather than deleted the moment they arrive.
        try:
            _migrate_legacy_recordings(self.recordings_dir)
        except Exception:
            # Nothing about moving old files is worth failing construction over.
            logger.warning("Migrating old recordings failed", exc_info=True)

    @property
    def temp_dir(self) -> Path:
        """Deprecated alias for :attr:`recordings_dir`, kept for existing callers."""
        return self.recordings_dir

    @property
    def is_recording(self) -> bool:
        return self._stream is not None

    @property
    def hit_duration_limit(self) -> bool:
        """True when the last take was cut short by the duration cap.

        Reset by :meth:`start_recording`.
        """
        return self._hit_duration_limit

    def _resolve_input_device_index(self) -> Optional[int]:
        """Resolve the PyAudio device index from a device name/id string.

        Returns ``None`` to use the default device.
        """
        if not self.audio_device or self.audio_device.lower() in ("default", ""):
            return None

        try:
            # If the user stored a numeric index, use it directly.
            return int(self.audio_device)
        except ValueError:
            pass

        # Otherwise try to match by name (case-insensitive substring).
        target = self.audio_device.lower()
        for i in range(self._pyaudio.get_device_count()):
            info = self._pyaudio.get_device_info_by_index(i)
            if (
                info.get("maxInputChannels", 0) > 0
                and target in str(info.get("name", "")).lower()
            ):
                return i

        # Fall back to default if no match.
        return None

    def _cleanup_old_recordings(self, keep: Optional[int] = None) -> None:
        """Remove the oldest WAVs in the recordings directory, keeping *keep* of them.

        The take currently being recorded is never a deletion candidate. It cannot be
        trusted to sort as the newest file: its WAV does not exist for most of the take,
        and when it is finally written its modification time is still older than any
        recording the user copied or touched in the meantime.
        """
        if keep is None:
            keep = MAX_RETAINED_RECORDINGS

        in_flight = self.output_path
        store = DictationStore(self.recordings_dir)
        # Unknown legacy takes may be the user's missing dictation. Never guess that
        # they succeeded. Only completed audio is disposable; transcripts stay.
        others = [p for p in self.recordings_dir.glob("*.wav")
                  if p != in_flight and store.read(p)["state"] == "completed"]
        try:
            others.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            # A file vanished mid-scan; the next take will prune it.
            logger.debug("Could not sort %s for pruning", self.recordings_dir, exc_info=True)
            return

        # The in-flight take counts against the retention budget once it is on disk,
        # so the folder settles at exactly *keep* files rather than one over.
        limit = keep - 1 if in_flight is not None and in_flight.exists() else keep
        for old in others[max(limit, 0):]:
            try:
                old.unlink()
            except OSError:
                pass

    def start_recording(self) -> None:
        with self._lock:
            if self._stream is not None:
                if self._stop_event.is_set():
                    if self._recording_thread is not None and self._recording_thread.is_alive():
                        raise OSError("The microphone is still stopping. Your audio is saved; try again shortly.")
                    self._finalize_locked()
                else:
                    return
            if self._wav_writer is not None:
                self._close_wav()
            self._frames = []
            self._set_volume_level(0.0)
            self._stop_event.clear()
            self._hit_duration_limit = False
            self._finalized_path = None
            self.output_path = self.recordings_dir / f"recording_{uuid.uuid4().hex}.wav"
            # Create a readable WAV before recording starts. writeframes patches the
            # header on each chunk; flush + fsync commits each captured chunk to disk.
            self._wav_file = self.output_path.open("w+b")
            self._wav_writer = wave.open(self._wav_file, "wb")
            self._wav_writer.setnchannels(self.channels)
            self._wav_writer.setsampwidth(self._pyaudio.get_sample_size(self.audio_format))
            self._wav_writer.setframerate(self.sample_rate)
            self._wav_writer.writeframes(b"")
            self._wav_file.flush()
            DictationStore(self.recordings_dir).update(self.output_path, state="recording")

            try:
                try:
                    self._open_input_stream()
                except OSError:
                    # PortAudio's device list can become stale after sleep or USB changes.
                    logger.warning("Microphone open failed; refreshing audio devices", exc_info=True)
                    self._pyaudio.terminate()
                    self._pyaudio = pyaudio.PyAudio()
                    self._open_input_stream()
            except Exception:
                self._close_wav()
                DictationStore(self.recordings_dir).update(self.output_path, state="failed", error="Microphone could not be opened")
                raise
            self._recording_thread = threading.Thread(target=self._record, daemon=True)
            self._recording_thread.start()
            # Retention scans parse journals and touch the disk. Run them after the
            # microphone is already capturing so a large history cannot delay onset.
            threading.Thread(target=self._cleanup_old_recordings, daemon=True).start()
            logger.info("Recording started: %s", self.output_path.name)

    def _open_input_stream(self) -> None:
        self._stream = self._pyaudio.open(
            format=self.audio_format,
            channels=self.channels,
            rate=self.sample_rate,
            input=True,
            input_device_index=self._resolve_input_device_index(),
            frames_per_buffer=self.chunk_size,
        )

    def _record(self) -> None:
        deadline: Optional[float] = None
        if self.max_duration_seconds and self.max_duration_seconds > 0:
            deadline = time.monotonic() + self.max_duration_seconds

        reached_limit = False
        while not self._stop_event.is_set() and self._stream is not None:
            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                # Update the UI-facing meter as soon as the device delivers a chunk.
                # WAV flush/fsync can stall on slow laptop storage and must not make
                # the live signal appear frozen.
                self._update_volume_level(data)
                self._frames.append(data)
                self._wav_writer.writeframes(data)
                self._wav_file.flush()
                os.fsync(self._wav_file.fileno())
            except Exception:
                # Device unplugged or stream closed under us: end the take, keep frames.
                logger.warning("Audio capture or save failed; ending capture", exc_info=True)
                if self.on_capture_error is not None:
                    self.on_capture_error("Audio capture stopped unexpectedly. Saved audio remains in Dictation History and will be transcribed.")
                break
            if deadline is not None and time.monotonic() >= deadline:
                reached_limit = True
                break
        self._set_volume_level(0.0)

        if reached_limit:
            self._auto_stop()

    def _auto_stop(self) -> None:
        """Cut the take short at the duration cap, from inside the capture thread.

        The WAV is finalized here rather than discarded: push-to-talk does eventually
        release, and a late :meth:`stop_recording` must still get the audio back.
        """
        self._stop_event.set()
        with self._lock:
            self._hit_duration_limit = True
            path = self._finalize_locked()

        logger.warning(
            "Recording hit the %gs duration cap and was stopped automatically",
            self.max_duration_seconds,
        )

        callback = self.on_max_duration_reached
        if callback is None:
            return
        # Outside the lock: the callback hands off to the UI and must never be able to
        # deadlock against a concurrent stop_recording().
        try:
            callback(path)
        except Exception:
            logger.exception("on_max_duration_reached callback failed")

    def _set_volume_level(self, value: float) -> None:
        with self._level_lock:
            self._volume_level = max(0.0, min(1.0, value))

    def _update_volume_level(self, data: bytes) -> None:
        if not data:
            self._set_volume_level(0.0)
            return

        samples = array("h")
        samples.frombytes(data)
        if not samples:
            self._set_volume_level(0.0)
            return

        square_sum = sum(sample * sample for sample in samples)
        rms = (square_sum / len(samples)) ** 0.5
        normalized = min(1.0, rms / 32768.0)

        with self._level_lock:
            current = self._volume_level
            smoothing = 0.35 if normalized > current else 0.12
            self._volume_level = current + (normalized - current) * smoothing

    def get_volume_level(self) -> float:
        with self._level_lock:
            return self._volume_level

    def _join_recording_thread(self) -> None:
        """Wait for the capture thread, never from the capture thread itself.

        The guard matters: the auto-stop path runs on that thread and can reach
        :meth:`stop_recording` through its callback.
        """
        thread = self._recording_thread
        if thread is None or thread is threading.current_thread():
            return
        thread.join(timeout=_THREAD_JOIN_TIMEOUT_SECONDS)
        if thread.is_alive():
            raise OSError("The microphone did not stop in time. Captured audio remains saved on disk.")

    def _close_wav(self) -> None:
        try:
            if self._wav_writer is not None:
                self._wav_writer.close()
        finally:
            self._wav_writer = None
            if self._wav_file is not None:
                self._wav_file.close()
                self._wav_file = None

    def _finalize_locked(self) -> Optional[Path]:
        """Close the stream and write the WAV. Caller must hold ``self._lock``."""
        if self._stream is None:
            # Already finalized - by the duration cap, or by an earlier stop.
            return self._finalized_path

        stream = self._stream
        try:
            stream.stop_stream()
            stream.close()
        except Exception:
            # Expected when the device vanished mid-take; the frames are already ours.
            logger.debug("Closing the input stream failed", exc_info=True)
        self._stream = None
        self._set_volume_level(0.0)
        self._close_wav()

        frames = self._frames
        self._frames = []
        if not frames:
            DictationStore(self.recordings_dir).update(self.output_path, state="failed", error="No audio captured")
            self._finalized_path = None
            return None

        path = self.output_path
        DictationStore(self.recordings_dir).update(path, state="pending")

        threading.Thread(target=self._cleanup_old_recordings, daemon=True).start()
        self._finalized_path = path
        logger.info("Recording saved: %s (%d frames)", path.name, sum(len(chunk) for chunk in frames) // (2 * self.channels))
        return path

    def stop_recording(self) -> Optional[Path]:
        # The join happens outside the locked region on purpose: the capture thread
        # takes the same lock to finalize an auto-stop, so joining while holding it
        # would deadlock for the full join timeout.
        self._stop_event.set()
        self._join_recording_thread()
        with self._lock:
            return self._finalize_locked()

    def terminate(self) -> None:
        self._stop_event.set()
        self._join_recording_thread()
        with self._lock:
            if self._stream is not None:
                try:
                    self._finalize_locked()
                except Exception:
                    # Shutdown path: a stream that will not close is not worth crashing on.
                    logger.debug("Closing the input stream failed", exc_info=True)
                self._stream = None
            self._set_volume_level(0.0)
            try:
                self._pyaudio.terminate()
            except Exception:
                # Shutdown path: the process is going away regardless.
                logger.debug("PyAudio terminate failed", exc_info=True)

    @staticmethod
    def list_input_devices() -> List[tuple]:
        """Return a list of available input devices as ``(index, name)`` tuples."""
        pa = pyaudio.PyAudio()
        devices: List[tuple] = []
        try:
            for i in range(pa.get_device_count()):
                info = pa.get_device_info_by_index(i)
                if info.get("maxInputChannels", 0) > 0:
                    devices.append((i, str(info.get("name", "Unknown"))))
        finally:
            pa.terminate()
        return devices
