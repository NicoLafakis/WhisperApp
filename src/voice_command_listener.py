"""
Voice Command Listener for WhisperApp
Continuously listens for voice commands using speech recognition

NOTE: This module requires speech_recognition which depends on deprecated
modules (aifc, audioop) that were removed in Python 3.13+.
For Python 3.13+, use WhisperVoiceListener instead.
"""
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None

from PyQt5.QtCore import QThread, pyqtSignal
import time
from typing import Callable, Optional


class VoiceCommandListener(QThread):
    """Thread that continuously listens for voice commands"""

    # Signals
    command_detected = pyqtSignal(str)  # Emits recognized text
    error_occurred = pyqtSignal(str)    # Emits error messages
    status_changed = pyqtSignal(str)    # Emits status updates

    def __init__(self, sensitivity='medium', language='en-US'):
        """
        Initialize voice command listener

        Args:
            sensitivity: Recognition sensitivity ('low', 'medium', 'high')
            language: Language code for recognition (default: 'en-US')

        Raises:
            ImportError: If speech_recognition is not available (Python 3.13+)
        """
        super().__init__()

        if not SPEECH_RECOGNITION_AVAILABLE:
            raise ImportError(
                "speech_recognition library is not available. "
                "This library depends on deprecated modules (aifc, audioop) "
                "that were removed in Python 3.13+. "
                "Please use WhisperVoiceListener instead."
            )

        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.is_listening = False
        self.should_stop = False
        self.language = language

        # Set sensitivity parameters
        self.set_sensitivity(sensitivity)

    def set_sensitivity(self, sensitivity: str):
        """
        Set recognition sensitivity

        Args:
            sensitivity: 'low', 'medium', or 'high'
        """
        sensitivity = sensitivity.lower()

        if sensitivity == 'low':
            self.recognizer.energy_threshold = 4000
            self.recognizer.dynamic_energy_threshold = False
            self.phrase_time_limit = 3
        elif sensitivity == 'high':
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            self.phrase_time_limit = 5
        else:  # medium (default)
            self.recognizer.energy_threshold = 1000
            self.recognizer.dynamic_energy_threshold = True
            self.phrase_time_limit = 4

        # Adjust for ambient noise
        self.recognizer.pause_threshold = 0.8

    def run(self):
        """Main thread loop - continuously listen for commands"""
        self.should_stop = False
        self.status_changed.emit("Initializing voice command listener...")

        try:
            # Initialize microphone
            self.microphone = sr.Microphone()

            # Adjust for ambient noise
            self.status_changed.emit("Calibrating for ambient noise...")
            with self.microphone as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)

            self.status_changed.emit("Voice command listener active")
            self.is_listening = True

            # Main listening loop
            while not self.should_stop:
                try:
                    self.listen_for_command()
                except Exception as e:
                    if not self.should_stop:
                        print(f"Listening error: {e}")
                        time.sleep(0.5)  # Brief pause before retrying

        except Exception as e:
            error_msg = f"Failed to initialize microphone: {e}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
        finally:
            self.is_listening = False
            self.status_changed.emit("Voice command listener stopped")

    def listen_for_command(self):
        """Listen for a single command"""
        try:
            with self.microphone as source:
                # Listen for audio
                audio = self.recognizer.listen(
                    source,
                    timeout=1,  # Wait up to 1 second for phrase to start
                    phrase_time_limit=self.phrase_time_limit
                )

            # Recognize speech using Google Speech Recognition
            try:
                text = self.recognizer.recognize_google(audio, language=self.language)
                if text:
                    print(f"Recognized: {text}")
                    self.command_detected.emit(text)

            except sr.UnknownValueError:
                # Speech was unintelligible
                pass
            except sr.RequestError as e:
                # API error
                error_msg = f"Speech recognition service error: {e}"
                print(error_msg)
                self.error_occurred.emit(error_msg)
                time.sleep(1)  # Wait before retrying

        except sr.WaitTimeoutError:
            # No speech detected in timeout period - this is normal
            pass
        except Exception as e:
            if not self.should_stop:
                print(f"Listen error: {e}")
                time.sleep(0.5)

    def stop_listening(self):
        """Stop the listening thread"""
        self.should_stop = True
        self.is_listening = False
        self.status_changed.emit("Stopping voice command listener...")

    def is_active(self) -> bool:
        """Check if listener is actively listening"""
        return self.is_listening and not self.should_stop


class VoiceCommandListenerOffline(QThread):
    """
    Alternative voice command listener using Vosk for offline recognition
    This is an optional implementation for offline use
    """

    # Signals
    command_detected = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    status_changed = pyqtSignal(str)

    def __init__(self, model_path: Optional[str] = None, sensitivity='medium'):
        """
        Initialize offline voice command listener

        Args:
            model_path: Path to Vosk model (if None, will try to use default)
            sensitivity: Recognition sensitivity

        Note:
            This is an alternative offline implementation using Vosk.
            Vosk does not depend on the deprecated audio modules.
        """
        super().__init__()
        self.model_path = model_path
        self.is_listening = False
        self.should_stop = False
        self.vosk_model = None
        self.recognizer = None

    def run(self):
        """Main thread loop - continuously listen for commands"""
        self.should_stop = False
        self.status_changed.emit("Initializing offline voice recognition...")

        try:
            # Try to import vosk
            try:
                import vosk
                import pyaudio
            except ImportError:
                error_msg = "Vosk not installed. Please install with: pip install vosk"
                self.error_occurred.emit(error_msg)
                return

            # Load model
            if not self.model_path:
                error_msg = "Vosk model path not specified"
                self.error_occurred.emit(error_msg)
                return

            try:
                self.vosk_model = vosk.Model(self.model_path)
                self.recognizer = vosk.KaldiRecognizer(self.vosk_model, 16000)
            except Exception as e:
                error_msg = f"Failed to load Vosk model: {e}"
                self.error_occurred.emit(error_msg)
                return

            # Initialize audio
            p = pyaudio.PyAudio()
            stream = p.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=8000
            )
            stream.start_stream()

            self.status_changed.emit("Offline voice command listener active")
            self.is_listening = True

            # Main listening loop
            while not self.should_stop:
                try:
                    data = stream.read(4000, exception_on_overflow=False)

                    if self.recognizer.AcceptWaveform(data):
                        result = self.recognizer.Result()
                        # Parse JSON result
                        import json
                        result_dict = json.loads(result)
                        text = result_dict.get('text', '')

                        if text:
                            print(f"Recognized (offline): {text}")
                            self.command_detected.emit(text)

                except Exception as e:
                    if not self.should_stop:
                        print(f"Offline listening error: {e}")
                        time.sleep(0.5)

            # Cleanup
            stream.stop_stream()
            stream.close()
            p.terminate()

        except Exception as e:
            error_msg = f"Offline voice recognition error: {e}"
            print(error_msg)
            self.error_occurred.emit(error_msg)
        finally:
            self.is_listening = False
            self.status_changed.emit("Offline voice command listener stopped")

    def stop_listening(self):
        """Stop the listening thread"""
        self.should_stop = True
        self.is_listening = False

    def is_active(self) -> bool:
        """Check if listener is actively listening"""
        return self.is_listening and not self.should_stop
