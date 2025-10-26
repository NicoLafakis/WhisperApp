"""
Whisper-based Voice Command Listener for JARVIS
Continuously captures audio, detects speech, and transcribes using OpenAI Whisper
"""
import pyaudio
import wave
import threading
import time
import numpy as np
from PyQt5.QtCore import QThread, pyqtSignal
from pathlib import Path
import tempfile
from typing import Optional
from collections import deque


class WhisperVoiceListener(QThread):
    """
    Advanced voice command listener using Whisper API
    Features:
    - Continuous audio capture with Voice Activity Detection (VAD)
    - Wake word detection ("Hey Jarvis")
    - Intelligent audio chunking
    - Superior transcription quality
    """

    # Signals
    command_detected = pyqtSignal(str)      # Emits recognized text
    wake_word_detected = pyqtSignal()       # Emits when "Hey Jarvis" detected
    error_occurred = pyqtSignal(str)        # Emits error messages
    status_changed = pyqtSignal(str)        # Emits status updates
    listening_state_changed = pyqtSignal(bool)  # True when actively listening for commands

    def __init__(self, transcription_service, sensitivity='medium', wake_word='jarvis', language=None):
        """
        Initialize Whisper voice command listener

        Args:
            transcription_service: TranscriptionService instance for Whisper API
            sensitivity: VAD sensitivity ('low', 'medium', 'high')
            wake_word: Wake word to activate (default: 'jarvis')
            language: Language code for Whisper (None for auto-detect)
        """
        super().__init__()
        self.transcription_service = transcription_service
        self.language = language
        self.wake_word = wake_word.lower()
        self.is_listening = False
        self.should_stop = False

        # Audio settings (optimized for Whisper)
        self.chunk = 1024
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000  # 16kHz is optimal for Whisper
        self.sample_width = 2  # 16-bit = 2 bytes

        # VAD settings
        self.set_sensitivity(sensitivity)

        # Audio buffering
        self.audio_buffer = deque(maxlen=int(self.rate / self.chunk * 10))  # 10 seconds max
        self.recording_frames = []
        self.is_speech_active = False
        self.silence_duration = 0
        self.silence_threshold = 1.5  # seconds of silence before processing

        # Wake word mode
        self.wake_word_mode = True  # Start in wake word listening mode
        self.active_listening_timeout = 60  # seconds to stay active after wake word
        self.active_until = 0  # timestamp when to return to wake word mode

        # PyAudio
        self.audio = None
        self.stream = None

    def set_sensitivity(self, sensitivity: str):
        """
        Set VAD sensitivity

        Args:
            sensitivity: 'low', 'medium', or 'high'
        """
        sensitivity = sensitivity.lower()

        if sensitivity == 'low':
            self.energy_threshold = 4000
            self.min_phrase_length = 0.5  # seconds
        elif sensitivity == 'high':
            self.energy_threshold = 300
            self.min_phrase_length = 0.3
        else:  # medium (default)
            self.energy_threshold = 1000
            self.min_phrase_length = 0.4

    def calculate_energy(self, audio_data: bytes) -> float:
        """
        Calculate RMS energy of audio data for VAD

        Args:
            audio_data: Raw audio bytes

        Returns:
            RMS energy value
        """
        # Convert bytes to numpy array
        audio_array = np.frombuffer(audio_data, dtype=np.int16)

        # Calculate RMS
        rms = np.sqrt(np.mean(np.square(audio_array.astype(np.float32))))
        return rms

    def is_speech(self, audio_data: bytes) -> bool:
        """
        Determine if audio data contains speech using energy-based VAD

        Args:
            audio_data: Raw audio bytes

        Returns:
            True if speech detected
        """
        energy = self.calculate_energy(audio_data)
        return energy > self.energy_threshold

    def save_audio_to_file(self, frames: list) -> Optional[str]:
        """
        Save audio frames to WAV file

        Args:
            frames: List of audio data frames

        Returns:
            Path to saved audio file, or None on error
        """
        if not frames:
            return None

        # Create temp file
        temp_dir = Path(tempfile.gettempdir()) / 'whisperapp'
        temp_dir.mkdir(exist_ok=True)
        audio_file = temp_dir / f'voice_command_{int(time.time())}.wav'

        try:
            with wave.open(str(audio_file), 'wb') as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.sample_width)
                wf.setframerate(self.rate)
                wf.writeframes(b''.join(frames))
            return str(audio_file)
        except Exception as e:
            print(f"Error saving audio: {e}")
            return None

    def process_audio_chunk(self, audio_file: str) -> Optional[str]:
        """
        Process audio chunk through Whisper API

        Args:
            audio_file: Path to audio file

        Returns:
            Transcribed text, or None on error
        """
        try:
            text = self.transcription_service.transcribe(
                audio_file,
                language=self.language
            )
            return text.strip() if text else None
        except Exception as e:
            print(f"Transcription error: {e}")
            self.error_occurred.emit(f"Transcription error: {e}")
            return None
        finally:
            # Clean up temp file
            try:
                Path(audio_file).unlink()
            except:
                pass

    def check_for_wake_word(self, text: str) -> bool:
        """
        Check if text contains wake word

        Args:
            text: Transcribed text

        Returns:
            True if wake word detected
        """
        text_lower = text.lower()

        # Check for various wake word patterns
        wake_patterns = [
            self.wake_word,
            f"hey {self.wake_word}",
            f"hi {self.wake_word}",
            f"hello {self.wake_word}",
            f"ok {self.wake_word}",
            f"okay {self.wake_word}",
        ]

        for pattern in wake_patterns:
            if pattern in text_lower:
                return True

        return False

    def activate_listening(self):
        """Activate command listening mode (after wake word detected)"""
        self.active_until = time.time() + self.active_listening_timeout
        self.wake_word_mode = False
        self.listening_state_changed.emit(True)
        self.status_changed.emit("JARVIS activated - listening for commands")

    def deactivate_listening(self):
        """Return to wake word listening mode"""
        self.wake_word_mode = True
        self.listening_state_changed.emit(False)
        self.status_changed.emit("Listening for wake word...")

    def is_active_listening(self) -> bool:
        """Check if in active command listening mode"""
        if not self.wake_word_mode:
            # Check if timeout expired
            if time.time() > self.active_until:
                self.deactivate_listening()
                return False
            return True
        return False

    def run(self):
        """Main thread loop - continuously capture and process audio"""
        self.should_stop = False
        self.status_changed.emit("Initializing Whisper voice listener...")

        try:
            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()

            # Open audio stream
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
                stream_callback=None
            )

            # Calibration phase
            self.status_changed.emit("Calibrating for ambient noise...")
            calibration_frames = []
            for _ in range(int(self.rate / self.chunk * 1)):  # 1 second
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                calibration_frames.append(data)

            # Adjust threshold based on ambient noise
            ambient_energy = np.mean([self.calculate_energy(frame) for frame in calibration_frames])
            self.energy_threshold = max(self.energy_threshold, ambient_energy * 1.5)

            self.status_changed.emit("Listening for wake word...")
            self.is_listening = True
            self.deactivate_listening()  # Start in wake word mode

            # Main capture loop
            while not self.should_stop:
                try:
                    # Read audio chunk
                    audio_data = self.stream.read(self.chunk, exception_on_overflow=False)

                    # Check for speech
                    if self.is_speech(audio_data):
                        # Speech detected - start/continue recording
                        if not self.is_speech_active:
                            self.is_speech_active = True
                            self.recording_frames = []
                            # Include some pre-roll from buffer
                            pre_roll = list(self.audio_buffer)[-20:] if len(self.audio_buffer) >= 20 else list(self.audio_buffer)
                            self.recording_frames.extend(pre_roll)

                        self.recording_frames.append(audio_data)
                        self.silence_duration = 0
                    else:
                        # No speech detected
                        if self.is_speech_active:
                            # Currently recording - add to frames and track silence
                            self.recording_frames.append(audio_data)
                            self.silence_duration += self.chunk / self.rate

                            # Check if silence threshold reached
                            if self.silence_duration >= self.silence_threshold:
                                # End of speech - process the recording
                                self.process_recording()
                                self.is_speech_active = False
                                self.silence_duration = 0
                                self.recording_frames = []

                    # Always buffer audio (for pre-roll)
                    self.audio_buffer.append(audio_data)

                except Exception as e:
                    if not self.should_stop:
                        print(f"Audio capture error: {e}")
                        time.sleep(0.1)

        except Exception as e:
            error_msg = f"Failed to initialize audio: {e}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
        finally:
            # Cleanup
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
            if self.audio:
                self.audio.terminate()

            self.is_listening = False
            self.status_changed.emit("Whisper voice listener stopped")

    def process_recording(self):
        """Process a completed recording through Whisper"""
        # Check minimum length
        duration = len(self.recording_frames) * self.chunk / self.rate
        if duration < self.min_phrase_length:
            return

        # Save to file
        audio_file = self.save_audio_to_file(self.recording_frames)
        if not audio_file:
            return

        # Transcribe
        text = self.process_audio_chunk(audio_file)
        if not text:
            return

        print(f"Whisper transcribed: {text}")

        # Check for wake word if in wake word mode
        if self.wake_word_mode:
            if self.check_for_wake_word(text):
                print(f"Wake word detected: {self.wake_word}")
                self.wake_word_detected.emit()
                self.activate_listening()

                # Remove wake word from text and emit remaining command if any
                text_lower = text.lower()
                for pattern in [f"hey {self.wake_word}", f"hi {self.wake_word}",
                               f"hello {self.wake_word}", f"ok {self.wake_word}",
                               f"okay {self.wake_word}", self.wake_word]:
                    if pattern in text_lower:
                        # Extract text after wake word
                        idx = text_lower.index(pattern) + len(pattern)
                        remaining = text[idx:].strip()
                        if remaining:
                            self.command_detected.emit(remaining)
                        return
            else:
                # No wake word - ignore in wake word mode
                return
        else:
            # Active listening mode - process all speech as commands
            self.command_detected.emit(text)
            # Extend active listening timeout
            self.active_until = time.time() + self.active_listening_timeout

    def stop_listening(self):
        """Stop the listening thread"""
        self.should_stop = True
        self.is_listening = False
        self.status_changed.emit("Stopping Whisper voice listener...")

    def is_active(self) -> bool:
        """Check if listener is actively running"""
        return self.is_listening and not self.should_stop

    def set_wake_word_mode(self, enabled: bool):
        """
        Enable/disable wake word mode

        Args:
            enabled: True for wake word mode, False for always-active mode
        """
        if enabled:
            self.deactivate_listening()
        else:
            self.activate_listening()
            self.active_until = time.time() + 999999  # Effectively infinite
