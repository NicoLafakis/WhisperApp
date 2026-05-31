import threading
import uuid
import wave
from pathlib import Path
from tempfile import gettempdir
from typing import List, Optional

import pyaudio


class AudioRecorder:
    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_size: int = 1024,
        audio_device: Optional[str] = None,
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.audio_format = pyaudio.paInt16
        self.audio_device = audio_device

        self._pyaudio = pyaudio.PyAudio()
        self._stream = None
        self._frames: List[bytes] = []
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self.temp_dir = Path(gettempdir()) / "whisperapp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_path: Optional[Path] = None

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
            self._stop_event.clear()
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
        while not self._stop_event.is_set() and self._stream is not None:
            try:
                data = self._stream.read(self.chunk_size, exception_on_overflow=False)
                self._frames.append(data)
            except Exception:
                break

    def stop_recording(self) -> Optional[Path]:
        with self._lock:
            if self._stream is None:
                return None
            self._stop_event.set()
            if self._recording_thread is not None:
                self._recording_thread.join(timeout=1.5)

            stream = self._stream
            self._stream = None

            try:
                stream.stop_stream()
                stream.close()
            except Exception:
                pass

            if not self._frames:
                return None

            path = self.output_path
            with wave.open(str(path), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self._pyaudio.get_sample_size(self.audio_format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(self._frames))

            self._cleanup_old_recordings()
            return path

    def terminate(self) -> None:
        with self._lock:
            self._stop_event.set()
            if self._stream is not None:
                try:
                    self._stream.stop_stream()
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            try:
                self._pyaudio.terminate()
            except Exception:
                pass

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
