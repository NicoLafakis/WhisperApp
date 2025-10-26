"""
Text-to-Speech System for JARVIS
Uses OpenAI TTS API to generate natural-sounding voice responses
"""
import pyaudio
import wave
import threading
from pathlib import Path
import tempfile
from typing import Optional
from queue import Queue, Empty
from openai import OpenAI
import httpx
from PyQt5.QtCore import QThread, pyqtSignal
import time


class TextToSpeechService:
    """Service for generating speech audio using OpenAI TTS"""

    def __init__(self, api_key: str, voice: str = "alloy", model: str = "tts-1",
                 speed: float = 1.0):
        """
        Initialize TTS service

        Args:
            api_key: OpenAI API key
            voice: Voice to use (alloy, echo, fable, onyx, nova, shimmer)
            model: TTS model (tts-1 or tts-1-hd)
            speed: Speaking speed (0.25 to 4.0)
        """
        self.voice = voice
        self.model = model
        self.speed = speed
        self.client = self._create_client(api_key) if api_key else None

    def _create_client(self, api_key: str) -> OpenAI:
        """Create OpenAI client with proper configuration"""
        http_client = httpx.Client(
            timeout=60.0,
            follow_redirects=True
        )
        return OpenAI(api_key=api_key, http_client=http_client)

    def update_api_key(self, api_key: str):
        """Update the API key"""
        self.client = self._create_client(api_key) if api_key else None

    def update_voice(self, voice: str):
        """Update the voice"""
        self.voice = voice

    def update_model(self, model: str):
        """Update the TTS model"""
        self.model = model

    def update_speed(self, speed: float):
        """Update speaking speed"""
        self.speed = max(0.25, min(4.0, speed))

    def generate_speech(self, text: str) -> Optional[str]:
        """
        Generate speech audio from text

        Args:
            text: Text to convert to speech

        Returns:
            Path to generated audio file, or None on error
        """
        if not self.client:
            print("TTS Error: API key not configured")
            return None

        if not text or not text.strip():
            return None

        try:
            # Create temp file for audio
            temp_dir = Path(tempfile.gettempdir()) / 'whisperapp'
            temp_dir.mkdir(exist_ok=True)
            audio_file = temp_dir / f'tts_{int(time.time() * 1000)}.mp3'

            # Generate speech
            response = self.client.audio.speech.create(
                model=self.model,
                voice=self.voice,
                input=text,
                speed=self.speed
            )

            # Save to file
            response.stream_to_file(str(audio_file))

            return str(audio_file)

        except Exception as e:
            print(f"TTS generation error: {e}")
            return None

    def is_configured(self) -> bool:
        """Check if API key is configured"""
        return self.client is not None


class AudioPlayer(QThread):
    """
    Thread-safe audio player with queue support
    Plays audio files sequentially without overlap
    """

    # Signals
    playback_started = pyqtSignal(str)  # Emits text being spoken
    playback_finished = pyqtSignal()     # Emits when playback completes
    error_occurred = pyqtSignal(str)     # Emits error messages
    queue_cleared = pyqtSignal()         # Emits when queue is cleared

    def __init__(self):
        """Initialize audio player"""
        super().__init__()
        self.audio_queue = Queue()
        self.should_stop = False
        self.is_playing = False
        self.current_playback = None
        self.allow_interrupt = True

    def add_to_queue(self, audio_file: str, text: str = ""):
        """
        Add audio file to playback queue

        Args:
            audio_file: Path to audio file
            text: Original text (for display/logging)
        """
        self.audio_queue.put({
            "file": audio_file,
            "text": text
        })

    def clear_queue(self):
        """Clear all pending audio from queue"""
        # Clear the queue
        while not self.audio_queue.empty():
            try:
                item = self.audio_queue.get_nowait()
                # Delete the file
                try:
                    Path(item["file"]).unlink()
                except:
                    pass
            except Empty:
                break

        self.queue_cleared.emit()

    def stop_playback(self):
        """Stop current playback and clear queue"""
        self.clear_queue()
        self.is_playing = False
        if self.current_playback:
            self.current_playback = None

    def run(self):
        """Main playback thread loop"""
        self.should_stop = False

        while not self.should_stop:
            try:
                # Wait for audio file with timeout
                try:
                    audio_item = self.audio_queue.get(timeout=0.5)
                except Empty:
                    continue

                audio_file = audio_item["file"]
                text = audio_item["text"]

                # Play the audio
                self.play_audio_file(audio_file, text)

                # Clean up temp file
                try:
                    Path(audio_file).unlink()
                except:
                    pass

            except Exception as e:
                print(f"Audio player error: {e}")
                self.error_occurred.emit(str(e))
                time.sleep(0.1)

    def play_audio_file(self, audio_file: str, text: str = ""):
        """
        Play an audio file

        Args:
            audio_file: Path to audio file (MP3)
            text: Original text being spoken
        """
        try:
            self.is_playing = True
            self.current_playback = audio_file
            self.playback_started.emit(text)

            # Convert MP3 to WAV for playback
            # Note: This requires pydub for MP3 support
            # For simplicity, we'll use a basic approach
            self._play_mp3_file(audio_file)

            self.is_playing = False
            self.current_playback = None
            self.playback_finished.emit()

        except Exception as e:
            print(f"Playback error: {e}")
            self.error_occurred.emit(str(e))
            self.is_playing = False
            self.current_playback = None

    def _play_mp3_file(self, mp3_file: str):
        """
        Play MP3 file using PyAudio
        Note: This requires conversion or a library like pydub
        For now, we'll use a simple approach with pygame or similar

        Args:
            mp3_file: Path to MP3 file
        """
        try:
            # Import pygame for MP3 playback
            import pygame

            # Initialize pygame mixer
            pygame.mixer.init()

            # Load and play
            pygame.mixer.music.load(mp3_file)
            pygame.mixer.music.play()

            # Wait for playback to finish
            while pygame.mixer.music.get_busy() and self.is_playing:
                time.sleep(0.1)

            pygame.mixer.music.stop()
            pygame.mixer.quit()

        except ImportError:
            # Fallback: Try using Windows Media Player COM object
            self._play_with_windows_media_player(mp3_file)
        except Exception as e:
            print(f"MP3 playback error: {e}")
            raise

    def _play_with_windows_media_player(self, audio_file: str):
        """
        Fallback: Play audio using Windows Media Player COM

        Args:
            audio_file: Path to audio file
        """
        try:
            import comtypes.client as cc

            wmp = cc.CreateObject("WMPlayer.OCX")
            wmp.URL = audio_file
            wmp.controls.play()

            # Wait for playback to finish
            while wmp.playState != 1 and self.is_playing:  # 1 = Stopped
                time.sleep(0.1)

            wmp.controls.stop()

        except Exception as e:
            print(f"Windows Media Player playback error: {e}")
            raise

    def stop_thread(self):
        """Stop the playback thread"""
        self.should_stop = True
        self.is_playing = False
        self.clear_queue()


class TextToSpeechManager:
    """
    High-level TTS manager combining generation and playback
    """

    def __init__(self, api_key: str, voice: str = "alloy", model: str = "tts-1",
                 speed: float = 1.0):
        """
        Initialize TTS manager

        Args:
            api_key: OpenAI API key
            voice: Voice to use
            model: TTS model
            speed: Speaking speed
        """
        self.tts_service = TextToSpeechService(api_key, voice, model, speed)
        self.audio_player = AudioPlayer()
        self.audio_player.start()

    def speak(self, text: str, interrupt: bool = False):
        """
        Speak text using TTS

        Args:
            text: Text to speak
            interrupt: If True, clear queue and speak immediately
        """
        if not text or not text.strip():
            return

        if interrupt:
            self.audio_player.stop_playback()

        # Generate audio
        audio_file = self.tts_service.generate_speech(text)
        if audio_file:
            # Add to playback queue
            self.audio_player.add_to_queue(audio_file, text)

    def stop_speaking(self):
        """Stop current speech and clear queue"""
        self.audio_player.stop_playback()

    def is_speaking(self) -> bool:
        """Check if currently speaking"""
        return self.audio_player.is_playing

    def update_voice(self, voice: str):
        """Update TTS voice"""
        self.tts_service.update_voice(voice)

    def update_model(self, model: str):
        """Update TTS model"""
        self.tts_service.update_model(model)

    def update_speed(self, speed: float):
        """Update speaking speed"""
        self.tts_service.update_speed(speed)

    def update_api_key(self, api_key: str):
        """Update API key"""
        self.tts_service.update_api_key(api_key)

    def cleanup(self):
        """Clean up resources"""
        self.audio_player.stop_thread()
        self.audio_player.wait()

    def is_configured(self) -> bool:
        """Check if TTS is configured"""
        return self.tts_service.is_configured()


# Available voices and their characteristics
AVAILABLE_VOICES = {
    "alloy": "Neutral, balanced voice suitable for most applications",
    "echo": "Warm, male-sounding voice with clear pronunciation",
    "fable": "Expressive, slightly whimsical voice",
    "onyx": "Deep, authoritative male voice - great for JARVIS",
    "nova": "Friendly, energetic female voice",
    "shimmer": "Soft, gentle female voice"
}


def get_voice_info() -> dict:
    """
    Get information about available voices

    Returns:
        Dictionary of voice names and descriptions
    """
    return AVAILABLE_VOICES
