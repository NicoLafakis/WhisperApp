from unittest.mock import MagicMock

import pytest
from PyQt5.QtCore import QObject

from whisperapp.main import WhisperTrayApp
from whisperapp.transcription_service import TranscriptionErrorKind, TranscriptionResult
from whisperapp.dictation_store import DictationStore


@pytest.fixture
def tray(tmp_path):
    # Exercise real controller methods without registering hotkeys or opening a mic.
    controller = WhisperTrayApp.__new__(WhisperTrayApp)
    QObject.__init__(controller)
    controller._is_recording = False
    controller._is_starting = False
    controller._is_stopping = False
    controller._stop_after_start = False
    controller._audio_thread = None
    controller._live_worker = None
    controller._live_result = None
    controller._live_pending_path = None
    controller._live_inserted = False
    controller._live_typed_phrases = []
    controller._live_partial_paths = set()
    controller._live_focus_lost = False
    controller._live_error_message = ""
    controller._closing = False
    controller._is_transcribing = False
    controller._retry_thread = None
    controller._retry_job_path = None
    controller._last_recording = tmp_path / "recording_test.wav"
    controller._last_recording.write_bytes(b"saved audio")
    controller.retry_action = MagicMock()
    controller.recording_indicator = MagicMock()
    controller.notify = MagicMock()
    controller.set_status = MagicMock()
    controller._report_failure = MagicMock()
    controller.settings = {"model": "gpt-transcribe", "language": "en"}
    controller.transcription_service = MagicMock()
    controller.copy_action = MagicMock()
    controller.text_inserter = MagicMock()
    controller._closing = False
    controller._worker_thread = None
    controller._active_job_path = controller._last_recording
    controller._indicator_job_path = controller._last_recording
    controller._capture_target = 123
    controller.text_inserter.foreground_window.return_value = 123
    controller._paste_targets = {str(controller._last_recording): 123}
    controller.store = DictationStore(tmp_path)
    controller.store.enqueue(controller._last_recording, "gpt-transcribe", "en")
    return controller


def test_failed_transcription_can_retry_saved_audio(tray, monkeypatch):
    worker = MagicMock()
    worker.isRunning.return_value = False
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
    tray._is_stopping = True
    worker = type("FailedStop", (), {"operation": "stop", "error": OSError("disk full")})()
    tray._on_audio_operation_finished(worker)
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
    def insert(**kwargs):
        tray.recording_indicator.hide_indicator.assert_not_called()
        return True

    tray.text_inserter.insert_text.side_effect = insert
    tray._on_transcription_finished(TranscriptionResult(text="Automatic dictation"))
    tray.text_inserter.insert_text.assert_called_once_with(text="Automatic dictation", auto_copy=True)
    tray.set_status.assert_called_with("Ready")
    tray.recording_indicator.finish.assert_called_once()


def test_stop_keeps_progress_visible_while_transcription_is_queued(tray):
    tray._is_recording = True
    tray._is_stopping = True
    tray._start_transcription = MagicMock()
    worker = type("SavedStop", (), {"operation": "stop", "error": None,
                                      "result": tray._last_recording})()
    tray._on_audio_operation_finished(worker)
    tray.recording_indicator.hide_indicator.assert_not_called()
    tray._start_transcription.assert_called_once_with(tray._last_recording)


def test_transient_error_keeps_retry_progress_visible(tray):
    tray._is_transcribing = True
    tray._on_transcription_finished(TranscriptionResult(
        error_kind=TranscriptionErrorKind.CONNECTION_FAILED,
        message="Connection interrupted",
    ))
    tray.recording_indicator.hide_indicator.assert_not_called()
    tray.recording_indicator.set_state.assert_called_with("RETRYING")
    tray.recording_indicator.finish.assert_not_called()


def test_older_result_does_not_replace_newer_queued_progress(tray, tmp_path):
    newer = tmp_path / "newer.wav"
    newer.write_bytes(b"saved audio")
    tray._indicator_job_path = newer
    tray._paste_targets.clear()
    tray._is_transcribing = True

    tray._on_transcription_partial("Older dictation preview")
    tray.recording_indicator.set_state.assert_not_called()
    tray._on_transcription_finished(TranscriptionResult(text="Older dictation result"))

    tray.recording_indicator.finish.assert_not_called()
    tray.recording_indicator.set_state.assert_not_called()
    tray.set_status.assert_not_called()
    assert tray._indicator_job_path == newer


def test_older_retry_does_not_replace_newer_queued_progress(tray, tmp_path):
    newer = tmp_path / "newer.wav"
    newer.write_bytes(b"saved audio")
    tray._indicator_job_path = newer
    tray._is_transcribing = True

    tray._on_transcription_finished(TranscriptionResult(
        error_kind=TranscriptionErrorKind.CONNECTION_FAILED,
        message="Connection interrupted",
    ))

    tray.recording_indicator.set_state.assert_not_called()
    tray.recording_indicator.finish.assert_not_called()
    tray.set_status.assert_not_called()
    assert tray._indicator_job_path == newer


def test_successful_text_goes_to_clipboard_when_focus_changed(tray):
    tray.text_inserter.foreground_window.return_value = 999
    tray.settings["auto_copy"] = True
    tray._on_transcription_finished(TranscriptionResult(text="Newest dictation"))
    tray.text_inserter.insert_text.assert_not_called()
    tray.text_inserter.copy_text.assert_called_once_with("Newest dictation")


def test_completed_text_replaces_clipboard_during_a_new_recording(tray):
    tray._is_recording = True
    tray.settings["auto_copy"] = True
    tray._on_transcription_finished(TranscriptionResult(text="Earlier take result"))
    tray.text_inserter.copy_text.assert_called_once_with("Earlier take result")
