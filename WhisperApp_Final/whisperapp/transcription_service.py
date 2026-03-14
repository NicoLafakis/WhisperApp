from pathlib import Path
from typing import Optional

import httpx
from openai import OpenAI


class TranscriptionService:
    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    def configure(self, api_key: str) -> None:
        api_key = (api_key or "").strip()
        if not api_key:
            self._client = None
            return

        http_client = httpx.Client(timeout=60.0, follow_redirects=True)
        self._client = OpenAI(api_key=api_key, http_client=http_client)

    def test_api_key(self, api_key: str) -> None:
        http_client = httpx.Client(timeout=60.0, follow_redirects=True)
        client = OpenAI(api_key=api_key.strip(), http_client=http_client)
        client.models.list()

    def transcribe(self, wav_path: Path, model: str, language: str) -> str:
        if self._client is None:
            return "Error: API key not configured"

        try:
            with wav_path.open("rb") as audio_file:
                kwargs = {
                    "model": model,
                    "file": audio_file,
                }
                if language:
                    kwargs["language"] = language
                transcript = self._client.audio.transcriptions.create(**kwargs)
            return transcript.text.strip()
        except Exception as exc:
            return f"Error: {exc}"
