"""Regression tests for defect D3 - runaway recording with no duration guard.

See docs/FINDINGS-2026-08-27-no-transcription-output.md.

A stuck push-to-talk left the recorder running for roughly 83 minutes and produced a
160,272,428 byte WAV. There was no duration cap, so the recording only ended when the
user noticed - and the upload that followed was a guaranteed failure.

These tests use a deliberately tiny cap so they finish in well under a second; the
real default is only checked for sanity, never for its exact value.
"""

from __future__ import annotations

import time
import wave
from pathlib import Path
from typing import List, Optional

import pytest

from whisperapp import audio_recorder as ar
from whisperapp import transcription_service as svc


FAST_CAP_SECONDS = 0.15
STOP_TIMEOUT_SECONDS = 5.0


@pytest.fixture
def make_recorder(fake_pyaudio):
    """Build recorders that are always torn down, even when a test times out."""
    built: List[ar.AudioRecorder] = []

    def _make(**kwargs) -> ar.AudioRecorder:
        recorder = ar.AudioRecorder(**kwargs)
        built.append(recorder)
        return recorder

    yield _make

    for recorder in built:
        try:
            recorder.terminate()
        except Exception as exc:  # best-effort teardown: never mask the test's own failure
            print(f"teardown of {recorder!r} failed: {exc!r}")


def _wait_until(predicate, timeout: float = STOP_TIMEOUT_SECONDS) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def _frame_count(path: Path) -> int:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes()


def test_default_duration_cap_keeps_recordings_under_the_upload_limit():
    """The cap must exist as a named constant and be a size the API will actually accept.

    Asserting the relationship rather than the number: whatever default is chosen, a
    full-length recording at the recorder's own format has to fit in one upload.
    """
    cap = ar.MAX_RECORDING_SECONDS

    assert cap > 0
    assert cap >= 60, "a cap under a minute would cut off normal dictation"

    worst_case_bytes = cap * 16000 * 2  # 16 kHz, mono, 16-bit - the recorder's defaults
    assert worst_case_bytes <= svc.MAX_UPLOAD_BYTES, (
        f"{cap}s at 16 kHz mono 16-bit is {worst_case_bytes} bytes, over the "
        f"{svc.MAX_UPLOAD_BYTES} byte upload limit"
    )


def test_recorder_stops_itself_at_the_duration_cap(make_recorder, fake_pyaudio):
    recorder = make_recorder(max_duration_seconds=FAST_CAP_SECONDS)

    started = time.monotonic()
    recorder.start_recording()
    assert recorder.is_recording is True

    stopped = _wait_until(lambda: recorder.is_recording is False)
    elapsed = time.monotonic() - started

    assert stopped is True, (
        f"recorder was still running {elapsed:.2f}s after a "
        f"{FAST_CAP_SECONDS}s cap - it never stopped itself"
    )
    assert elapsed >= FAST_CAP_SECONDS, "stopped before the cap was reached"
    assert recorder.hit_duration_limit is True

    stream = fake_pyaudio.instance.streams[0]
    assert stream.stopped is True
    assert stream.closed is True


def test_auto_stop_finalizes_the_wav_and_notifies_the_caller(make_recorder):
    """The caller has to learn about the auto-stop, or the UI stays stuck on Recording."""
    notified: List[Optional[Path]] = []

    recorder = make_recorder(
        max_duration_seconds=FAST_CAP_SECONDS,
        on_max_duration_reached=notified.append,
    )
    recorder.start_recording()

    assert _wait_until(lambda: bool(notified)), "on_max_duration_reached was never called"

    path = notified[0]
    assert isinstance(path, Path), f"expected the finalized WAV path, got {path!r}"
    assert path.exists()
    assert _frame_count(path) > 0, "the audio captured before the cap was thrown away"


def test_stop_recording_after_auto_stop_returns_the_finalized_path(make_recorder):
    """A late key release must not lose the recording or blow up."""
    notified: List[Optional[Path]] = []

    recorder = make_recorder(
        max_duration_seconds=FAST_CAP_SECONDS,
        on_max_duration_reached=notified.append,
    )
    recorder.start_recording()
    assert _wait_until(lambda: bool(notified))

    assert recorder.stop_recording() == notified[0]


def test_recorder_under_the_cap_is_unaffected(make_recorder):
    recorder = make_recorder(max_duration_seconds=30.0)
    recorder.start_recording()
    time.sleep(0.05)

    path = recorder.stop_recording()

    assert recorder.hit_duration_limit is False
    assert path is not None
    assert _frame_count(path) > 0


def test_stale_audio_device_is_refreshed_and_recording_retried(make_recorder, fake_pyaudio, monkeypatch):
    from unittest.mock import MagicMock
    recorder = make_recorder()
    original_open = fake_pyaudio.instance.open
    opened = MagicMock(side_effect=[OSError(-9999, "Unanticipated host error"), original_open()])
    monkeypatch.setattr(fake_pyaudio.instance, "open", opened)
    recorder.start_recording()
    time.sleep(0.02)
    assert recorder.stop_recording() is not None
    assert opened.call_count == 2
    assert fake_pyaudio.instance.terminated


def test_capture_read_failure_notifies_controller(make_recorder, fake_pyaudio, monkeypatch):
    from unittest.mock import MagicMock
    stream = fake_pyaudio.instance.open()
    stream.read = MagicMock(side_effect=OSError("device disconnected"))
    monkeypatch.setattr(fake_pyaudio.instance, "open", lambda **kwargs: stream)
    errors = []
    recorder = make_recorder(on_capture_error=errors.append)
    recorder.start_recording()
    assert _wait_until(lambda: bool(errors))
    assert "capture stopped" in errors[0]
    assert recorder.stop_recording() is None
