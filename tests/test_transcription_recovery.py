from unittest.mock import MagicMock

import pytest
from PyQt5.QtCore import QObject

from whisperapp.main import WhisperTrayApp
from whisperapp.transcription_service import TranscriptionErrorKind, TranscriptionResult


@pytest.fixture
def tray(tmp_path):
    # Exercise real controller methods without registering hotkeys or opening a mic.
    controller = WhisperTrayApp.__new__(WhisperTrayApp)
    QObject.__init__(controller)
    controller._is_recording = False
    controller._is_transcribing = False
    controller._last_recording = tmp_path / "recording.wav"
    controller._last_recording.write_bytes(b"saved audio")
    controller.retry_action = MagicMock()
    controller.notify = MagicMock()
    controller.set_status = MagicMock()
    controller._report_failure = MagicMock()
    controller.settings = {"model": "gpt-transcribe", "language": "en"}
    controller.transcription_service = MagicMock()
    controller.copy_action = MagicMock()
    controller.text_inserter = MagicMock()
    return controller


def test_failed_transcription_can_retry_saved_audio(tray, monkeypatch):
    worker = MagicMock()
    factory = MagicMock(return_value=worker)
    monkeypatch.setattr("whisperapp.main.TranscriptionThread", factory)
    tray._is_transcribing = True
    tray._on_transcription_finished(TranscriptionResult(
        error_kind=TranscriptionErrorKind.CONNECTION_FAILED, message="offline"
    ))
    assert not tray._is_transcribing
    tray.retry_action.setEnabled.assert_called_with(True)
    tray.retry_last_recording()
    assert factory.call_args.kwargs["wav_path"] == tray._last_recording
    assert tray._is_transcribing
    tray.retry_action.setEnabled.assert_called_with(False)
    worker.start.assert_called_once()


@pytest.mark.parametrize("busy", ["_is_recording", "_is_transcribing"])
def test_retry_does_not_interrupt_active_work(tray, busy):
    setattr(tray, busy, True)
    tray._start_transcription = MagicMock()
    tray.retry_last_recording()
    tray._start_transcription.assert_not_called()


def test_retry_missing_recording_is_reported(tray):
    tray._last_recording.unlink()
    tray._start_transcription = MagicMock()
    tray.retry_last_recording()
    tray._start_transcription.assert_not_called()
    tray.notify.assert_called_once()
    assert tray._last_recording is None
    tray.retry_action.setEnabled.assert_called_with(False)


def test_save_failure_does_not_leave_app_stuck_transcribing(tray):
    tray._is_recording = True
    tray.recording_indicator = MagicMock()
    tray.audio_recorder = MagicMock()
    tray.audio_recorder.stop_recording.side_effect = OSError("disk full")
    tray.on_hotkey_released()
    assert not tray._is_recording
    assert not tray._is_transcribing
    tray.notify.assert_called_once()
    tray.retry_action.setEnabled.assert_called_with(True)


def test_paste_exception_retains_text_for_recovery(tray):
    tray.text_inserter.insert_text.side_effect = RuntimeError("clipboard busy")
    tray._on_transcription_finished(TranscriptionResult(text="Keep this dictation"))
    assert tray._last_text == "Keep this dictation"
    tray.copy_action.setEnabled.assert_called_with(True)
    tray.copy_last_transcription()
    tray.text_inserter.copy_text.assert_called_once_with("Keep this dictation")


def test_successful_transcription_is_automatically_inserted(tray):
    tray._on_transcription_finished(TranscriptionResult(text="Automatic dictation"))
    tray.text_inserter.insert_text.assert_called_once_with(text="Automatic dictation", auto_copy=True)
    tray.set_status.assert_called_with("Ready")
