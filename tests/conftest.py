"""Shared fixtures for the WhisperApp regression suite.

Everything here is offline: no OpenAI calls, no PyAudio devices, no Qt event loop.
The fakes deliberately mirror the *real* libraries' behaviour, because the defects
these tests pin down were caused by the real behaviour of those libraries
(see docs/FINDINGS-2026-08-27-no-transcription-output.md).
"""

from __future__ import annotations

import time
from functools import lru_cache
from typing import Any, Callable, Dict, List, Optional
from unittest.mock import MagicMock

import httpx
import pyaudio
import pytest
from openai import OpenAI


@pytest.fixture(autouse=True)
def disable_live_network_for_ui_tests(monkeypatch):
    """Keep controller tests deterministic; realtime protocol tests use a fake SDK."""
    from whisperapp import main

    class Signal:
        def connect(self, *_args, **_kwargs):
            pass

    class IdleLiveWorker:
        def __init__(self, *_args, **_kwargs):
            self.ready = Signal()
            self.phrase_completed = Signal()
            self.failed = Signal()
            self.completed = Signal()
            self.finished = Signal()

        def start(self):
            pass

        def wait(self, *_args):
            return True

        def isRunning(self):
            return False

        def finish_recording(self):
            pass

        def enqueue_audio(self, _chunk):
            return False

    monkeypatch.setattr(main, "LiveTranscriptionThread", IdleLiveWorker)


# --------------------------------------------------------------------------------------
# OpenAI error factory
# --------------------------------------------------------------------------------------

# Verbatim from the live 429 recorded in docs/FINDINGS-2026-08-27-no-transcription-output.md.
QUOTA_MESSAGE = (
    "You have no credits remaining. Add credits to continue using the API at "
    "https://platform.openai.com/settings/organization/billing/."
)


@lru_cache(maxsize=1)
def _error_client() -> OpenAI:
    """A client used only to build exceptions. It never issues a request."""
    return OpenAI(api_key="sk-unit-test-key-never-sent")


def openai_error(
    status_code: int,
    *,
    message: str,
    error_type: Optional[str] = None,
    code: Optional[str] = None,
    path: str = "/v1/audio/transcriptions",
) -> Exception:
    """Build the exception the openai SDK itself would raise for a given error response.

    Routing through the client's own ``_make_status_error_from_response`` is deliberate:
    it guarantees the exception class and the ``status_code`` / ``type`` / ``code`` /
    ``body`` attributes match openai 2.x exactly, rather than a shape we invented.
    ``test_openai_error_fixtures_match_the_installed_sdk`` pins that shape.
    """
    envelope = {"error": {"message": message, "type": error_type, "code": code}}
    request = httpx.Request("POST", f"https://api.openai.com{path}")
    response = httpx.Response(status_code, json=envelope, request=request)
    return _error_client()._make_status_error_from_response(response)


@pytest.fixture
def quota_error() -> Exception:
    """HTTP 429 caused by an exhausted credit balance - the failure that bit us."""
    return openai_error(
        429,
        message=QUOTA_MESSAGE,
        error_type="insufficient_quota",
        code="credit_balance_exhausted",
    )


@pytest.fixture
def rate_limit_error() -> Exception:
    """HTTP 429 caused by request throttling - retryable, unlike a quota failure."""
    return openai_error(
        429,
        message="Rate limit reached for whisper-1 in organization org-x on requests per min.",
        error_type="requests",
        code="rate_limit_exceeded",
    )


@pytest.fixture
def auth_error() -> Exception:
    return openai_error(
        401,
        message="Incorrect API key provided: sk-***. You can find your API key at "
        "https://platform.openai.com/account/api-keys.",
        error_type="invalid_request_error",
        code="invalid_api_key",
    )


@pytest.fixture
def too_large_error() -> Exception:
    """HTTP 413 from the server when an oversized file is uploaded anyway."""
    return openai_error(
        413,
        message="Maximum content size limit (26214400) exceeded (160272428 bytes read)",
        error_type="server_error",
    )


# --------------------------------------------------------------------------------------
# Fake keyboard module
# --------------------------------------------------------------------------------------


class _Registration:
    """One live entry in the fake listener's key store."""

    def __init__(self, key: str, kind: str) -> None:
        self.key = key
        self.kind = kind

    def __repr__(self) -> str:  # shows up in assertion failures
        return f"<{self.kind} hook on {self.key!r}>"


class FakeKeyboard:
    """Stand-in for the parts of the ``keyboard`` package that HotkeyListener uses.

    It reproduces the shared-entry behaviour of the real ``keyboard.hook_key``
    (keyboard/__init__.py lines 482-504), which stores
    ``_hooks[callback] = _hooks[key] = _hooks[remove_] = remove_``.

    Two registrations against the same key therefore overwrite ``_hooks[key]``, and the
    second ``unhook`` raises ``KeyError`` on ``del _hooks[key]`` *before* it reaches the
    line that removes the callback from the listener store - so the handler leaks.
    That is defect D4.
    """

    def __init__(self, key_states: Optional[Dict[str, bool]] = None) -> None:
        self._hooks: Dict[Any, Callable[[], None]] = {}
        self.registered: List[_Registration] = []
        self.unhook_calls = 0
        self._key_states = dict(key_states or {})

    def _hook_key(self, key: str, callback: Callable[[Any], Any], kind: str) -> Callable[[], None]:
        # The real library wraps the caller's handler, so each registration has its own
        # callback object even when the same handler is passed twice.
        wrapper = lambda event: callback(event)  # noqa: E731
        entry = _Registration(key, kind)
        self.registered.append(entry)

        def remove_() -> None:
            del self._hooks[wrapper]
            del self._hooks[key]
            del self._hooks[remove_]
            self.registered.remove(entry)

        self._hooks[wrapper] = self._hooks[key] = self._hooks[remove_] = remove_
        return remove_

    def on_press_key(self, key, callback, suppress=False):
        return self._hook_key(key, callback, "press")

    def on_release_key(self, key, callback, suppress=False):
        return self._hook_key(key, callback, "release")

    def unhook(self, remove):
        self.unhook_calls += 1
        self._hooks[remove]()

    unhook_key = unhook

    def unhook_all(self) -> None:
        self._hooks.clear()
        self.registered.clear()

    def is_pressed(self, key: str) -> bool:
        return self._key_states.get(key, True)


class RaisingKeyboard(FakeKeyboard):
    """A ``keyboard`` whose per-handler unhook always fails, however it is called."""

    def unhook(self, remove):
        self.unhook_calls += 1
        raise KeyError("space")

    unhook_key = unhook


@pytest.fixture
def fake_keyboard(monkeypatch) -> FakeKeyboard:
    from whisperapp import hotkey_listener

    fake = FakeKeyboard()
    monkeypatch.setattr(hotkey_listener, "keyboard", fake)
    return fake


@pytest.fixture
def raising_keyboard(monkeypatch) -> RaisingKeyboard:
    from whisperapp import hotkey_listener

    fake = RaisingKeyboard()
    monkeypatch.setattr(hotkey_listener, "keyboard", fake)
    return fake


# --------------------------------------------------------------------------------------
# Fake PyAudio
# --------------------------------------------------------------------------------------

SILENT_CHUNK = b"\x00\x01" * 1024  # 1024 frames of 16-bit mono, near-silent


class FakeStream:
    def __init__(self, chunk: bytes, read_delay: float) -> None:
        self._chunk = chunk
        self._read_delay = read_delay
        self.reads = 0
        self.stopped = False
        self.closed = False

    def read(self, frames, exception_on_overflow=False) -> bytes:
        if self.closed:
            raise OSError("stream is closed")
        time.sleep(self._read_delay)
        self.reads += 1
        return self._chunk

    def stop_stream(self) -> None:
        self.stopped = True

    def close(self) -> None:
        self.closed = True


class FakePyAudioInstance:
    def __init__(self, chunk: bytes, read_delay: float) -> None:
        self._chunk = chunk
        self._read_delay = read_delay
        self.streams: List[FakeStream] = []
        self.terminated = False

    def open(self, **kwargs) -> FakeStream:
        stream = FakeStream(self._chunk, self._read_delay)
        self.streams.append(stream)
        return stream

    def get_sample_size(self, audio_format) -> int:
        return 2  # 16-bit

    def get_device_count(self) -> int:
        return 0

    def get_device_info_by_index(self, index):
        raise IndexError(index)

    def terminate(self) -> None:
        self.terminated = True


class FakePyAudioModule:
    # The real constant, so the recorder's sample-width maths stays honest.
    paInt16 = pyaudio.paInt16

    def __init__(self, chunk: bytes = SILENT_CHUNK, read_delay: float = 0.002) -> None:
        self.instance = FakePyAudioInstance(chunk, read_delay)

    def PyAudio(self) -> FakePyAudioInstance:  # noqa: N802 - mirrors the real API
        return self.instance


@pytest.fixture
def fake_pyaudio(monkeypatch, tmp_path) -> FakePyAudioModule:
    """Replace PyAudio with an in-memory fake and redirect recordings to tmp_path.

    Both redirects matter. AudioRecorder prunes old WAVs in its output directory and
    migrates takes out of the legacy one, and both of those are directories the
    installed app really uses - the Documents one holds the user's own recordings.
    """
    from whisperapp import audio_recorder

    fake = FakePyAudioModule()
    monkeypatch.setattr(audio_recorder, "pyaudio", fake)
    # A separate subfolder, not tmp_path itself: on Windows the legacy "whisperapp"
    # directory and the new "WhisperApp" one would otherwise be the same directory.
    documents = tmp_path / "Documents"
    monkeypatch.setattr(audio_recorder, "_documents_dir", lambda: documents)
    monkeypatch.setattr(audio_recorder, "gettempdir", lambda: str(tmp_path))
    return fake


# --------------------------------------------------------------------------------------
# Fake OpenAI client
# --------------------------------------------------------------------------------------


@pytest.fixture
def fake_openai(monkeypatch) -> MagicMock:
    """Intercept ``OpenAI(...)`` inside transcription_service and hand back a mock.

    Patching the constructor rather than the service's private ``_client`` keeps the
    tests on the public surface: both ``configure()`` and ``test_api_key()`` build their
    own client, and both end up with this mock.
    """
    from whisperapp import transcription_service

    client = MagicMock(name="OpenAIClient")
    monkeypatch.setattr(transcription_service, "OpenAI", MagicMock(return_value=client))
    return client


def transcript(text: str) -> MagicMock:
    """A stand-in for the SDK's Transcription response object."""
    response = MagicMock(name="Transcription")
    response.text = text
    return response
