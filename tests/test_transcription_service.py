"""Regression tests for defects D1 (error classification) and D2 (capability check).

See docs/FINDINGS-2026-08-27-no-transcription-output.md.

The app went silent because ``transcribe()`` collapsed every failure - including a
perfectly well-labelled HTTP 429 ``insufficient_quota`` - into an ``"Error: ..."``
string, and because "Test API Key" probed ``models.list()``, an endpoint that is not
quota-gated and answers 200 OK on a key with a zero credit balance.

These tests pin the replacement contract: a structured result carrying a
machine-checkable error kind, and a key check that exercises transcription itself.
"""

from __future__ import annotations

from pathlib import Path

import openai
import pytest

from tests.conftest import QUOTA_MESSAGE, openai_error, transcript
from whisperapp import transcription_service as svc


@pytest.fixture
def wav_path(tmp_path: Path) -> Path:
    path = tmp_path / "recording.wav"
    path.write_bytes(b"RIFF....WAVEfmt ")
    return path


@pytest.fixture
def service(fake_openai) -> "svc.TranscriptionService":
    instance = svc.TranscriptionService()
    instance.configure("sk-test-key")
    return instance


def _oversized(tmp_path: Path, limit: int) -> Path:
    """A file one byte past *limit*, created sparsely so the test stays fast."""
    path = tmp_path / "oversized.wav"
    with path.open("wb") as handle:
        handle.seek(limit)
        handle.write(b"\x00")
    assert path.stat().st_size == limit + 1
    return path


# --------------------------------------------------------------------------------------
# Fixture fidelity - guards the rest of the file against asserting on an invented shape
# --------------------------------------------------------------------------------------


def test_openai_error_fixtures_match_the_installed_sdk(quota_error, rate_limit_error, auth_error):
    assert isinstance(quota_error, openai.RateLimitError)
    assert quota_error.status_code == 429
    assert quota_error.type == "insufficient_quota"
    assert quota_error.code == "credit_balance_exhausted"
    assert quota_error.body["message"] == QUOTA_MESSAGE

    # Same status code, same exception class - only the body tells the two apart.
    assert isinstance(rate_limit_error, openai.RateLimitError)
    assert rate_limit_error.status_code == 429
    assert rate_limit_error.type != "insufficient_quota"

    assert isinstance(auth_error, openai.AuthenticationError)
    assert auth_error.status_code == 401


# --------------------------------------------------------------------------------------
# D1 - transcription failures are classified
# --------------------------------------------------------------------------------------


def test_successful_transcription_returns_text_and_no_error(service, fake_openai, wav_path):
    fake_openai.audio.transcriptions.create.return_value = transcript("  hello world  ")

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.ok is True
    assert result.error_kind is None
    assert result.text == "hello world"


def test_quota_exhaustion_is_classified_as_quota_not_rate_limit(service, fake_openai, wav_path, quota_error):
    """The headline case: a 429 carrying insufficient_quota is NOT a plain rate limit.

    Both arrive as openai.RateLimitError with status_code 429. Only the body
    distinguishes them, and the distinction changes what the user must do: add credits
    versus wait and retry.
    """
    fake_openai.audio.transcriptions.create.side_effect = quota_error

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.QUOTA_EXHAUSTED
    assert result.error_kind is not svc.TranscriptionErrorKind.RATE_LIMITED


def test_plain_rate_limit_is_classified_as_rate_limited(service, fake_openai, wav_path, rate_limit_error):
    fake_openai.audio.transcriptions.create.side_effect = rate_limit_error

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.RATE_LIMITED


def test_auth_failure_is_classified_as_auth(service, fake_openai, wav_path, auth_error):
    fake_openai.audio.transcriptions.create.side_effect = auth_error

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.AUTH_FAILED


def test_server_side_file_too_large_is_classified_as_file_too_large(
    service, fake_openai, wav_path, too_large_error
):
    fake_openai.audio.transcriptions.create.side_effect = too_large_error

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.FILE_TOO_LARGE


def test_unexpected_failure_is_classified_as_unknown(service, fake_openai, wav_path):
    fake_openai.audio.transcriptions.create.side_effect = RuntimeError("something exploded")

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.UNKNOWN


def test_unconfigured_service_is_classified_not_configured(fake_openai, wav_path):
    service = svc.TranscriptionService()
    service.configure("")

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.NOT_CONFIGURED


def test_failure_result_preserves_the_api_message(service, fake_openai, wav_path, quota_error):
    """The API named the fix ("add credits ... /billing/"). Do not throw that away."""
    fake_openai.audio.transcriptions.create.side_effect = quota_error

    result = service.transcribe(wav_path=wav_path, model="whisper-1", language="en")

    assert result.text == ""
    assert QUOTA_MESSAGE in result.message


# --------------------------------------------------------------------------------------
# D3 - oversized recordings are rejected before upload
# --------------------------------------------------------------------------------------


def test_oversized_recording_is_rejected_before_upload(service, fake_openai, tmp_path):
    """A 160 MB WAV must never reach the wire; OpenAI's limit is 25 MiB."""
    path = _oversized(tmp_path, svc.MAX_UPLOAD_BYTES)

    result = service.transcribe(wav_path=path, model="whisper-1", language="en")

    fake_openai.audio.transcriptions.create.assert_not_called()
    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.FILE_TOO_LARGE
    assert result.message.strip() != ""


def test_recording_at_the_limit_is_still_uploaded(service, fake_openai, tmp_path):
    """The guard must not be over-eager: a file exactly at the limit is valid."""
    path = tmp_path / "at_limit.wav"
    with path.open("wb") as handle:
        handle.seek(svc.MAX_UPLOAD_BYTES - 1)
        handle.write(b"\x00")
    fake_openai.audio.transcriptions.create.return_value = transcript("still fine")

    result = service.transcribe(wav_path=path, model="whisper-1", language="en")

    assert fake_openai.audio.transcriptions.create.called is True
    assert result.ok is True
    assert result.text == "still fine"


def test_max_upload_bytes_matches_the_openai_limit():
    assert svc.MAX_UPLOAD_BYTES == 25 * 1024 * 1024


# --------------------------------------------------------------------------------------
# D2 - the key check exercises the transcription capability
# --------------------------------------------------------------------------------------


def test_key_check_fails_when_quota_is_exhausted(fake_openai):
    """The exact production scenario: models.list() is happy, transcription 429s.

    Settings reported "API key is valid" for a key that could not transcribe a single
    second of audio. That false green is what sent the investigation away from billing.
    """
    fake_openai.models.list.return_value = ["whisper-1"]
    fake_openai.audio.transcriptions.create.side_effect = openai_error(
        429,
        message=QUOTA_MESSAGE,
        error_type="insufficient_quota",
        code="credit_balance_exhausted",
    )
    service = svc.TranscriptionService()

    result = service.test_api_key("sk-test-key")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.QUOTA_EXHAUSTED
    assert QUOTA_MESSAGE in result.message


def test_key_check_actually_calls_the_transcription_endpoint(fake_openai):
    fake_openai.audio.transcriptions.create.return_value = transcript("probe")
    service = svc.TranscriptionService()

    service.test_api_key("sk-test-key")

    assert fake_openai.audio.transcriptions.create.called is True


def test_key_check_passes_when_transcription_works(fake_openai):
    fake_openai.audio.transcriptions.create.return_value = transcript("probe")
    service = svc.TranscriptionService()

    result = service.test_api_key("sk-test-key")

    assert result.ok is True
    assert result.error_kind is None


def test_key_check_reports_auth_failure(fake_openai, auth_error):
    fake_openai.audio.transcriptions.create.side_effect = auth_error
    service = svc.TranscriptionService()

    result = service.test_api_key("sk-bad-key")

    assert result.ok is False
    assert result.error_kind is svc.TranscriptionErrorKind.AUTH_FAILED


@pytest.mark.parametrize("language", ["en", "fr", ""])
def test_gpt_transcribe_uses_plural_language_hints(service, fake_openai, wav_path, language):
    fake_openai.audio.transcriptions.create.return_value = transcript("  Bonjour  ")
    result = service.transcribe(wav_path, "gpt-transcribe", language)
    request = fake_openai.audio.transcriptions.create.call_args.kwargs
    assert request["model"] == "gpt-transcribe"
    assert "language" not in request
    if language:
        assert request["extra_body"] == {"languages": [language]}
    else:
        assert "extra_body" not in request
    assert result.text == "Bonjour"


def test_legacy_fallback_keeps_its_request_contract(service, fake_openai, wav_path):
    service.transcribe(wav_path, "whisper-1", "en")
    request = fake_openai.audio.transcriptions.create.call_args.kwargs
    assert request["language"] == "en"
    assert "extra_body" not in request


@pytest.mark.parametrize("model", ["gpt-transcribe", "whisper-1"])
def test_key_check_probes_selected_model(fake_openai, model):
    svc.TranscriptionService().test_api_key("sk-test-key", model=model)
    assert fake_openai.audio.transcriptions.create.call_args.kwargs["model"] == model


def test_key_check_defaults_to_new_model(fake_openai):
    svc.TranscriptionService().test_api_key("sk-test-key")
    assert fake_openai.audio.transcriptions.create.call_args.kwargs["model"] == "gpt-transcribe"
