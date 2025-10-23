"""
Transcription service using OpenAI Whisper API
"""
from openai import OpenAI
from pathlib import Path


class TranscriptionService:
    """Handles transcription using OpenAI Whisper"""

    def __init__(self, api_key):
        self.client = OpenAI(api_key=api_key) if api_key else None

    def update_api_key(self, api_key):
        """Update the API key"""
        self.client = OpenAI(api_key=api_key) if api_key else None

    def transcribe(self, audio_file_path, model="whisper-1", language=None):
        """
        Transcribe audio file using OpenAI Whisper

        Args:
            audio_file_path: Path to audio file
            model: Whisper model to use (default: whisper-1)
            language: Language code (e.g., 'en', 'es', 'fr')

        Returns:
            Transcribed text or None if error
        """
        if not self.client:
            return "Error: API key not configured"

        try:
            with open(audio_file_path, 'rb') as audio_file:
                params = {
                    "model": model,
                    "file": audio_file,
                }

                if language:
                    params["language"] = language

                transcript = self.client.audio.transcriptions.create(**params)
                return transcript.text.strip()
        except Exception as e:
            print(f"Transcription error: {e}")
            return f"Error: {str(e)}"

    def is_configured(self):
        """Check if API key is configured"""
        return self.client is not None
