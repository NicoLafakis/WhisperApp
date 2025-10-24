"""
Transcription service using OpenAI Whisper API
"""
from openai import OpenAI
import httpx
from pathlib import Path


class TranscriptionService:
    """Handles transcription using OpenAI Whisper"""

    def __init__(self, api_key):
        self.client = self._create_client(api_key) if api_key else None

    def _create_client(self, api_key):
        """Create OpenAI client with proper HTTP client configuration"""
        # Create httpx client without proxy to avoid compatibility issues
        http_client = httpx.Client(
            timeout=60.0,
            follow_redirects=True
        )
        return OpenAI(api_key=api_key, http_client=http_client)

    def update_api_key(self, api_key):
        """Update the API key"""
        self.client = self._create_client(api_key) if api_key else None

    def transcribe(self, audio_file_path, model="whisper-1", language=None):
        """
        Transcribe audio file using OpenAI Whisper

        Args:
            audio_file_path: Path to audio file
            model: Whisper model to use (default: whisper-1)
            language: Language code (e.g., 'en', 'es', 'fr')

        Returns:
            Transcribed text

        Raises:
            Exception: If transcription fails
        """
        if not self.client:
            raise Exception("API key not configured")

        with open(audio_file_path, 'rb') as audio_file:
            params = {
                "model": model,
                "file": audio_file,
            }

            if language:
                params["language"] = language

            transcript = self.client.audio.transcriptions.create(**params)
            return transcript.text.strip()

    def is_configured(self):
        """Check if API key is configured"""
        return self.client is not None
