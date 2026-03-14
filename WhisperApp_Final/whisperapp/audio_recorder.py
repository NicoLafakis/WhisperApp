import threading
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
    ) -> None:
        self.sample_rate = sample_rate
        self.channels = channels
        self.chunk_size = chunk_size
        self.audio_format = pyaudio.paInt16

        self._pyaudio = pyaudio.PyAudio()
        self._stream = None
        self._frames: List[bytes] = []
        self._recording_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self.temp_dir = Path(gettempdir()) / "whisperapp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.output_path = self.temp_dir / "recording.wav"

    def start_recording(self) -> None:
        with self._lock:
            if self._stream is not None:
                return
            self._frames = []
            self._stop_event.clear()
            self._stream = self._pyaudio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
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

            with wave.open(str(self.output_path), "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self._pyaudio.get_sample_size(self.audio_format))
                wf.setframerate(self.sample_rate)
                wf.writeframes(b"".join(self._frames))

            return self.output_path

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
