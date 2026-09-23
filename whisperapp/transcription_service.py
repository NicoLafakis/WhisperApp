import io
import logging
import math
import wave
from array import array
from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from pathlib import Path
from typing import Dict, Optional, Tuple

import httpx
import openai
from openai import OpenAI

from whisperapp.config_manager import DEFAULT_TRANSCRIPTION_MODEL


logger = logging.getLogger(__name__)


# OpenAI rejects any transcription upload larger than this.
# https://platform.openai.com/docs/guides/speech-to-text
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

BILLING_URL = "https://platform.openai.com/settings/organization/billing/"

# A 429 carries either of these when the account is out of credit rather than merely
# throttled. Same exception class, same status code - only the body tells them apart.
QUOTA_ERROR_TYPES = frozenset({"insufficient_quota"})
QUOTA_ERROR_CODES = frozenset({"insufficient_quota", "credit_balance_exhausted"})

# The key check uploads this much synthetic audio. OpenAI rejects clips under 0.1s.
PROBE_MODEL = DEFAULT_TRANSCRIPTION_MODEL
PROBE_FILENAME = "whisperapp-key-check.wav"
PROBE_SAMPLE_RATE = 16000
PROBE_DURATION_SECONDS = 0.25


class TranscriptionErrorKind(Enum):
    """Why a transcription (or a key check) failed, in terms the UI can act on."""

    NOT_CONFIGURED = "not_configured"
    QUOTA_EXHAUSTED = "quota_exhausted"
    RATE_LIMITED = "rate_limited"
    AUTH_FAILED = "auth_failed"
    FILE_TOO_LARGE = "file_too_large"
    CONNECTION_FAILED = "connection_failed"
    SERVICE_UNAVAILABLE = "service_unavailable"
    UNKNOWN = "unknown"


# Short headline per failure kind, for dialog titles and notification balloons.
ERROR_HEADLINES: Dict[TranscriptionErrorKind, str] = {
    TranscriptionErrorKind.NOT_CONFIGURED: "API Key Required",
    TranscriptionErrorKind.QUOTA_EXHAUSTED: "OpenAI Credits Exhausted",
    TranscriptionErrorKind.RATE_LIMITED: "Rate Limited",
    TranscriptionErrorKind.AUTH_FAILED: "API Key Rejected",
    TranscriptionErrorKind.FILE_TOO_LARGE: "Recording Too Long",
    TranscriptionErrorKind.CONNECTION_FAILED: "Connection Failed",
    TranscriptionErrorKind.SERVICE_UNAVAILABLE: "Transcription Service Unavailable",
    TranscriptionErrorKind.UNKNOWN: "Transcription Failed",
}

# Persistent tray-menu status per failure kind. Must read as a failure at a glance.
ERROR_STATUSES: Dict[TranscriptionErrorKind, str] = {
    TranscriptionErrorKind.NOT_CONFIGURED: "Failed: no API key",
    TranscriptionErrorKind.QUOTA_EXHAUSTED: "Failed: no OpenAI credits",
    TranscriptionErrorKind.RATE_LIMITED: "Failed: rate limited, retry shortly",
    TranscriptionErrorKind.AUTH_FAILED: "Failed: API key rejected",
    TranscriptionErrorKind.FILE_TOO_LARGE: "Failed: recording too long",
    TranscriptionErrorKind.CONNECTION_FAILED: "Failed: connection lost — retry recording",
    TranscriptionErrorKind.SERVICE_UNAVAILABLE: "Audio saved — service unavailable",
    TranscriptionErrorKind.UNKNOWN: "Failed: see log",
}


@dataclass(frozen=True)
class TranscriptionResult:
    """Outcome of a transcription attempt.

    On failure *text* is empty and *message* holds the API's own wording verbatim - the
    quota body names the billing page, which is the one thing the user actually needs.
    """

    text: str = ""
    error_kind: Optional[TranscriptionErrorKind] = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.error_kind is None


def api_message(exc: Exception) -> str:
    """The API's own error message, preferred over the SDK's wrapped repr."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        message = body.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()

    message = getattr(exc, "message", None)
    if isinstance(message, str) and message.strip():
        return message.strip()

    return str(exc).strip() or exc.__class__.__name__


def classify_error(exc: Exception) -> Tuple[TranscriptionErrorKind, str]:
    """Map an exception from the OpenAI SDK onto an actionable failure kind."""
    message = api_message(exc)

    if isinstance(exc, openai.APIConnectionError):
        return TranscriptionErrorKind.CONNECTION_FAILED, (
            "Could not reach OpenAI. Recordings are saved locally and temporary "
            "connection failures are retried automatically. Open Dictation History to recover audio or text."
        )

    if not isinstance(exc, openai.APIStatusError):
        return TranscriptionErrorKind.UNKNOWN, message

    status_code = exc.status_code
    if status_code >= 500:
        return TranscriptionErrorKind.SERVICE_UNAVAILABLE, message
    if status_code == 401:
        return TranscriptionErrorKind.AUTH_FAILED, message
    if status_code == 413:
        return TranscriptionErrorKind.FILE_TOO_LARGE, message
    if status_code == 429:
        # Quota exhaustion and plain throttling are both RateLimitError/429. Only the
        # body separates "add credits" from "wait and retry".
        if exc.type in QUOTA_ERROR_TYPES or exc.code in QUOTA_ERROR_CODES:
            return TranscriptionErrorKind.QUOTA_EXHAUSTED, message
        return TranscriptionErrorKind.RATE_LIMITED, message

    return TranscriptionErrorKind.UNKNOWN, message


@lru_cache(maxsize=1)
def _probe_clip_bytes() -> bytes:
    """A short synthetic WAV used to prove a key can really transcribe.

    A quiet tone rather than digital silence, and comfortably over the 0.1s minimum
    the API enforces.
    """
    frame_count = int(PROBE_SAMPLE_RATE * PROBE_DURATION_SECONDS)
    samples = array(
        "h",
        (
            int(1200 * math.sin(2 * math.pi * 440 * n / PROBE_SAMPLE_RATE))
            for n in range(frame_count)
        ),
    )

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(PROBE_SAMPLE_RATE)
        wf.writeframes(samples.tobytes())
    return buffer.getvalue()


class TranscriptionService:
    def __init__(self) -> None:
        self._client: Optional[OpenAI] = None

    @staticmethod
    def _build_http_client() -> httpx.Client:
        return httpx.Client(timeout=60.0, follow_redirects=True)

    def configure(self, api_key: str) -> None:
        api_key = (api_key or "").strip()
        if not api_key:
            self._client = None
            return

        # Retry scheduling belongs to the durable queue so it survives restarts.
        self._client = OpenAI(api_key=api_key, http_client=self._build_http_client(), max_retries=0)

    def test_api_key(self, api_key: str, model: str = PROBE_MODEL) -> TranscriptionResult:
        """Check that *api_key* can transcribe, not merely that it authenticates.

        Deliberately *not* ``models.list()``: that endpoint is not quota-gated and
        answers 200 OK on a key with a zero credit balance, which is exactly the false
        green that hid an exhausted account. Only a real POST to the transcription
        endpoint proves the capability, so this uploads a fraction of a second of
        synthetic audio.

        Returns a result; never raises.
        """
        api_key = (api_key or "").strip()
        if not api_key:
            return TranscriptionResult(
                error_kind=TranscriptionErrorKind.NOT_CONFIGURED,
                message="Enter an OpenAI API key first.",
            )

        try:
            client = OpenAI(
                api_key=api_key,
                http_client=self._build_http_client(),
                # A quota failure will never succeed on retry, and the user is waiting
                # on a dialog - answer on the first response.
                max_retries=0,
            )
            client.audio.transcriptions.create(
                model=model,
                file=(PROBE_FILENAME, _probe_clip_bytes(), "audio/wav"),
            )
        except Exception as exc:
            kind, message = classify_error(exc)
            logger.warning("API key check failed (%s): %s", kind.name, message)
            return TranscriptionResult(error_kind=kind, message=message)

        return TranscriptionResult(message="API key is valid and can transcribe audio.")

    def transcribe(
        self,
        wav_path: Path,
        model: str,
        language: str,
        on_partial=None,
    ) -> TranscriptionResult:
        if self._client is None:
            return TranscriptionResult(
                error_kind=TranscriptionErrorKind.NOT_CONFIGURED,
                message="No OpenAI API key is configured. Open Settings from the tray icon.",
            )

        oversized = self._reject_if_oversized(wav_path)
        if oversized is not None:
            return oversized

        try:
            with wav_path.open("rb") as audio_file:
                kwargs = {
                    "model": model,
                    "file": audio_file,
                }
                if language:
                    if model == DEFAULT_TRANSCRIPTION_MODEL:
                        # The new API uses plural language hints. extra_body also
                        # works with SDKs predating the new typed fields.
                        kwargs["extra_body"] = {"languages": [language]}
                    else:
                        kwargs["language"] = language
                if model == DEFAULT_TRANSCRIPTION_MODEL and on_partial is not None:
                    # The newer transcription models can stream progress once the
                    # completed WAV is uploaded. Whisper-1 does not support this API.
                    kwargs["stream"] = True
                    transcript = self._client.audio.transcriptions.create(**kwargs)
                    partial_text = ""
                    final_text = ""
                    for event in transcript:
                        event_type = getattr(event, "type", "")
                        if event_type == "transcript.text.delta":
                            partial_text += getattr(event, "delta", "") or ""
                            on_partial(partial_text)
                        elif event_type == "transcript.text.done":
                            final_text = getattr(event, "text", "") or partial_text
                    return TranscriptionResult(text=final_text.strip())
                transcript = self._client.audio.transcriptions.create(**kwargs)
        except Exception as exc:
            kind, message = classify_error(exc)
            logger.error("Transcription failed (%s): %s", kind.name, message, exc_info=True)
            return TranscriptionResult(error_kind=kind, message=message)

        return TranscriptionResult(text=(getattr(transcript, "text", "") or "").strip())

    @staticmethod
    def _reject_if_oversized(wav_path: Path) -> Optional[TranscriptionResult]:
        """Refuse an upload the API is certain to reject, before spending the bandwidth."""
        try:
            size = wav_path.stat().st_size
        except OSError:
            return None

        if size <= MAX_UPLOAD_BYTES:
            return None

        message = (
            f"The recording is {size / (1024 * 1024):.1f} MB. OpenAI accepts at most "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB per transcription. "
            "Record a shorter clip."
        )
        logger.error("Refusing oversized upload: %s (%d bytes)", wav_path, size)
        return TranscriptionResult(
            error_kind=TranscriptionErrorKind.FILE_TOO_LARGE,
            message=message,
        )
