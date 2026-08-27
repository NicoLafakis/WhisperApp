import logging
import threading
import time
import uuid
import wave
from array import array
from pathlib import Path
from tempfile import gettempdir
from typing import Callable, List, Optional

import pyaudio


logger = logging.getLogger(__name__)


# Hard ceiling on a single take. A stuck push-to-talk once ran for ~83 minutes and
# produced a 160 MB WAV that could never be uploaded. Ten minutes at the recorder's own
# format (16 kHz mono 16-bit) is 19.2 MB, comfortably inside OpenAI's 25 MB limit.
MAX_RECORDING_SECONDS = 600.0

# How long to wait for the capture thread to notice the stop flag and exit.
_THREAD_JOIN_TIMEOUT_SECONDS = 1.5


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        audio_device: Optional[str] = None,
        max_duration_seconds: float = MAX_RECORDING_SECONDS,
        on_max_duration_reached: Optional[Callable[[Optional[Path]], None]] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.audio_format = pyaudio.paInt16
        self.audio_device = audio_device
        self.max_duration_seconds = max_duration_seconds
        self.on_max_duration_reached = on_max_duration_reached

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

        self.temp_dir = Path(gettempdir()) / "whisperapp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_path: Optional[Path] = None

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

    def _cleanup_old_recordings(self, keep: int = 10) -> None:
        """Remove oldest WAV files in the temp directory, keeping *keep* most recent."""
        wav_files = sorted(
            self.temp_dir.glob("*.wav"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in wav_files[keep:]:
            try:
                old.unlink()
            except OSError:
                pass

    def start_recording(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._frames = []
            self._set_volume_level(0.0)
            self._stop_event.clear()
            self._hit_duration_limit = False
            self._finalized_path = None
            self.output_path = self.temp_dir / f"recording_{uuid.uuid4().hex}.wav"

            device_index = self._resolve_input_device_index()
            self._stream = self._pyaudio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk_size,
            )
            self._recording_thread = threading.Thread(target=self._record, daemon=True)
            self._recording_thread.start()

    def _record(self) -> None:
        deadline: Optional[float] = None
        if self.max_duration_seconds and self.max_duration_seconds > 0:
            deadline = time.monotonic() + self.max_duration_seconds

        reached_limit = False
        while not self._stop_event.is_set() and self._stream is not None:
            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                self._frames.append(data)
                self._update_volume_level(data)
            except Exception:
                # Device unplugged or stream closed under us: end the take, keep frames.
                logger.debug("Input stream read failed; ending capture", exc_info=True)
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

        frames = self._frames
        self._frames = []
        if not frames:
            self._finalized_path = None
            return None

        path = self.output_path
        with wave.open(str(path), "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self._pyaudio.get_sample_size(self.audio_format))
            wf.setframerate(self.sample_rate)
            wf.writeframes(b"".join(frames))

        self._cleanup_old_recordings()
        self._finalized_path = path
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
                    self._stream.stop_stream()
                    self._stream.close()
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
