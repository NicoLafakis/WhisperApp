"""
Audio recording module for WhisperApp
Handles microphone input and audio file creation
"""
import pyaudio
import wave
import threading
from pathlib import Path
import tempfile


class AudioRecorder:
    """Records audio from microphone"""

    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.recording_thread = None

        # Audio settings
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000  # 16kHz is optimal for Whisper

    def get_audio_devices(self):
        """Get list of available audio input devices"""
        devices = []
        for i in range(self.audio.get_device_count()):
            device_info = self.audio.get_device_info_by_index(i)
            if device_info['maxInputChannels'] > 0:
                devices.append({
                    'index': i,
                    'name': device_info['name']
                })
        return devices

    def start_recording(self, device_index=None):
        """Start recording audio"""
        if self.is_recording:
            return

        self.frames = []
        self.is_recording = True

        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.chunk
            )

            self.recording_thread = threading.Thread(target=self._record)
            self.recording_thread.start()
        except Exception as e:
            print(f"Error starting recording: {e}")
            self.is_recording = False

    def _record(self):
        """Internal recording loop"""
        while self.is_recording:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
            except Exception as e:
                print(f"Error during recording: {e}")
                break

    def stop_recording(self):
        """Stop recording and return audio file path"""
        if not self.is_recording:
            return None

        self.is_recording = False

        if self.recording_thread:
            self.recording_thread.join()

        if self.stream:
            self.stream.stop_stream()
            self.stream.close()

        if not self.frames:
            return None

        # Save to temporary file
        temp_dir = Path(tempfile.gettempdir()) / 'whisperapp'
        temp_dir.mkdir(exist_ok=True)
        audio_file = temp_dir / 'recording.wav'

        try:
            with wave.open(str(audio_file), 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(self.frames))
            return str(audio_file)
        except Exception as e:
            print(f"Error saving audio file: {e}")
            return None

    def cleanup(self):
        """Clean up audio resources"""
        if self.stream:
            self.stream.close()
        self.audio.terminate()
