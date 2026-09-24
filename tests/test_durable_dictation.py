import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock
import wave

import httpx
import json
import openai
import pytest
from PyQt5.QtWidgets import QApplication

from whisperapp import main
from whisperapp.dictation_store import DictationStore
from whisperapp.transcription_service import TranscriptionResult, TranscriptionService


def wav(path, seconds=0.1):
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x01\x00" * int(seconds * 16000))
    return path


def test_queue_restarts_after_reset_and_never_retranscribes_saved_text(tmp_path):
    path = wav(tmp_path / "recording_long.wav", seconds=90)
    store = DictationStore(tmp_path)
    store.enqueue(path, "gpt-transcribe", "en")
    store.update(path, state="transcribing", attempts=1)
    restarted = DictationStore(tmp_path)
    restarted.recover()
    assert restarted.next_job()["path"] == str(path)
    assert restarted.next_job()["attempts"] == 1
    restarted.complete(path, "The entire paragraph survives the restart.")
    another_restart = DictationStore(tmp_path)
    another_restart.recover()
    assert another_restart.next_job() is None
    assert another_restart.text(path) == "The entire paragraph survives the restart."


def test_retry_respects_backoff(tmp_path):
    path = wav(tmp_path / "recording_backoff.wav")
    store = DictationStore(tmp_path)
    store.update(path, state="retry", next_retry=100)
    assert store.next_job(now=99) is None
    assert store.next_job(now=100)["path"] == str(path)


def test_fresh_dictation_is_processed_before_older_due_retry(tmp_path):
    store = DictationStore(tmp_path)
    older = wav(tmp_path / "recording_older.wav")
    fresh = wav(tmp_path / "recording_fresh.wav")
    store.enqueue(older, "gpt-transcribe", "en")
    store.enqueue(fresh, "gpt-transcribe", "en")
    store.update(older, state="retry", created=10, next_retry=20)
    store.update(fresh, state="pending", created=30)
    assert store.next_job(now=40)["path"] == str(fresh)


def test_background_retry_waits_while_a_new_recording_is_captured(tmp_path):
    store = DictationStore(tmp_path)
    older = wav(tmp_path / "recording_retry.wav")
    store.enqueue(older, "gpt-transcribe", "en")
    store.update(older, state="retry", next_retry=20)
    assert store.next_job(now=40, include_retries=False) is None
    assert store.next_job(now=40)["path"] == str(older)


def test_restart_retains_failed_job_and_resumes_it_when_due(tmp_path):
    path = wav(tmp_path / "recording_failed.wav", seconds=90)
    store = DictationStore(tmp_path)
    store.enqueue(path, "gpt-transcribe", "en")
    store.update(path, state="retry", next_retry=100, attempts=4, error="Connection reset")
    restarted = DictationStore(tmp_path)
    restarted.recover()
    assert restarted.next_job(now=99) is None
    assert restarted.next_job(now=101)["attempts"] == 4
    assert restarted.text(path) == ""
    assert path.exists()


def test_corrupt_metadata_keeps_audio_available_for_manual_recovery(tmp_path):
    path = wav(tmp_path / "recording_corrupt.wav")
    path.with_suffix(".json").write_text("{truncated")
    store = DictationStore(tmp_path)
    store.recover()
    assert store.jobs()[0]["state"] == "saved"
    assert path.exists()


@pytest.mark.parametrize("metadata", [{}, {"state": []}, {"state": "retry", "created": [], "next_retry": "tomorrow", "attempts": None},
                                      {"state": "pending", "created": float("nan"), "next_retry": float("inf"), "model": 1}])
def test_parseable_damaged_journal_does_not_block_recovery(tmp_path, metadata):
    path = wav(tmp_path / "recording_damaged.wav")
    path.with_suffix(".json").write_text(json.dumps(metadata))
    store = DictationStore(tmp_path)
    store.recover()
    assert len(store.jobs()) == 1
    assert isinstance(store.jobs()[0]["state"], str)
    store.next_job()


def test_one_locked_interrupted_wav_does_not_block_other_recovery(tmp_path, monkeypatch):
    store = DictationStore(tmp_path)
    first = wav(tmp_path / "recording_locked.wav")
    second = wav(tmp_path / "recording_ok.wav")
    for path in (first, second):
        store.update(path, state="recording")
    original = store._repair_interrupted_wav
    def repair(path):
        if path == first:
            raise PermissionError("locked")
        original(path)
    monkeypatch.setattr(store, "_repair_interrupted_wav", repair)
    store.recover()
    assert store.next_job()["path"] == str(second)


def test_interrupted_wav_header_recovers_all_appended_audio(tmp_path):
    path = wav(tmp_path / "recording_interrupted.wav")
    initial = path.stat().st_size
    store = DictationStore(tmp_path)
    store.update(path, state="recording")
    with path.open("ab") as handle:
        handle.write(b"\x01\x00" * 1024)
    store.recover()
    with wave.open(str(path)) as recording:
        assert recording.getnframes() == (initial - 44) // 2 + 1024


def test_text_survives_failed_metadata_write(tmp_path, monkeypatch):
    path = wav(tmp_path / "recording_saved.wav")
    store = DictationStore(tmp_path)
    store.enqueue(path, "gpt-transcribe", "en")
    monkeypatch.setattr(store, "update", MagicMock(side_effect=OSError("disk full")))
    with pytest.raises(OSError):
        store.complete(path, "Saved before metadata failed")
    restarted = DictationStore(tmp_path)
    assert restarted.read(path)["state"] == "completed"
    assert restarted.text(path) == "Saved before metadata failed"
    assert restarted.next_job() is None


def test_history_retains_text_after_completed_audio_is_pruned(tmp_path):
    path = wav(tmp_path / "recording_history.wav")
    store = DictationStore(tmp_path)
    store.complete(path, "Permanent transcription")
    path.unlink()
    assert store.jobs()[0]["state"] == "completed"
    assert store.text(path) == "Permanent transcription"


def test_worker_saves_text_before_emitting_completion(tmp_path):
    app = QApplication.instance() or QApplication([])
    path = wav(tmp_path / "recording_worker.wav")
    store = DictationStore(tmp_path)
    service = MagicMock()
    service.transcribe.return_value = TranscriptionResult(text="Persisted before UI delivery")
    worker = main.TranscriptionThread(service, path, "gpt-transcribe", "en", store)
    observed = []
    worker.completed.connect(lambda result: observed.append(store.text(path)))
    worker.run()
    assert observed == ["Persisted before UI delivery"]


def test_shutdown_waits_for_worker_to_persist_completed_text(controller, tmp_path):
    app, tray = controller
    path = wav(tmp_path / "recording_shutdown.wav")
    service = MagicMock()
    def delayed_transcription(**kwargs):
        time.sleep(0.05)
        return TranscriptionResult(text="Saved while the app was quitting")
    service.transcribe.side_effect = delayed_transcription
    tray._worker_thread = main.TranscriptionThread(service, path, "gpt-transcribe", "en", tray.store)
    tray._worker_thread.start()
    tray.cleanup()
    assert tray.store.text(path) == "Saved while the app was quitting"
    assert not tray._worker_thread.isRunning()


@pytest.fixture
def controller(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    config = MagicMock()
    config.get_settings.return_value = {"api_key": "test", "model": "gpt-transcribe"}
    recorder = MagicMock()
    recorder.recordings_dir = tmp_path
    inserter = MagicMock()
    inserter.foreground_window.return_value = 123
    for name, instance in (("ConfigManager", config), ("AudioRecorder", recorder), ("TextInserter", inserter)):
        monkeypatch.setattr(main, name, MagicMock(return_value=instance))
    monkeypatch.setattr(main, "HotkeyListener", MagicMock())
    monkeypatch.setattr(main, "RecordingIndicator", MagicMock())
    monkeypatch.setattr(main, "QSystemTrayIcon", MagicMock())
    tray = main.WhisperTrayApp(app)
    tray._capture_target = 123
    yield app, tray
    tray.cleanup()
    app.aboutToQuit.disconnect(tray.cleanup)


def pump(app, condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.001)
    assert condition(), "Timed out waiting for dictation flow"


def test_35_long_dictations_with_transport_reset_every_thirtieth(controller, monkeypatch, tmp_path):
    app, tray = controller
    calls = 0
    def transport(request):
        nonlocal calls
        calls += 1
        if calls % 30 == 0:
            raise httpx.ConnectError("[WinError 10054] An existing connection was forcibly closed by the remote host", request=request)
        text = f"Full paragraph from request {calls}"
        events = [
            {"type": "transcript.text.delta", "delta": text},
            {"type": "transcript.text.done", "text": text},
        ]
        body = "".join(f"data: {json.dumps(event)}\n\n" for event in events) + "data: [DONE]\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body.encode())
    tray.transcription_service._client = openai.OpenAI(
        api_key="test", max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(transport)),
    )
    # Advance only the retry scheduling clock, with no sleep and no real network.
    monkeypatch.setattr(main, "time", SimpleNamespace(time=lambda: 0))
    for index in range(35):
        path = wav(tmp_path / f"recording_{index:03}.wav", seconds=90)
        tray._start_transcription(path)
        pump(app, lambda: bool(tray.store.text(path)) and not tray._is_transcribing)
        assert tray._worker_thread.wait(1000)
    assert calls == 36
    assert len([job for job in tray.store.jobs() if job["state"] == "completed"]) == 35
    assert tray.text_inserter.insert_text.call_count == 35  # a transient reset still completes normal dictation


def test_recording_is_accepted_while_previous_upload_is_running(controller):
    app, tray = controller
    tray._is_transcribing = True
    tray.on_hotkey_pressed()
    pump(app, lambda: tray._audio_thread is not None and not tray._audio_thread.isRunning())
    tray.audio_recorder.start_recording.assert_called_once()
    assert tray._is_recording


def test_fresh_dictation_completes_while_older_retry_is_still_in_flight(controller, tmp_path):
    app, tray = controller
    retry = wav(tmp_path / "recording_retry_in_flight.wav")
    fresh = wav(tmp_path / "recording_fresh_in_flight.wav")
    retry_started = threading.Event()
    release_retry = threading.Event()

    def transcribe(*, wav_path, **_kwargs):
        if wav_path == retry:
            retry_started.set()
            release_retry.wait(3)
            return TranscriptionResult(text="Old recovery")
        return TranscriptionResult(text="Fresh dictation")

    tray.transcription_service.transcribe = transcribe
    tray.store.enqueue(retry, "gpt-transcribe", "en")
    tray.store.update(retry, state="retry", next_retry=0, created=1)
    tray._process_queue()
    assert retry_started.wait(1)
    try:
        tray._start_transcription(fresh)
        pump(app, lambda: tray.store.text(fresh) == "Fresh dictation", timeout=1)
        assert not tray.store.text(retry)
    finally:
        release_retry.set()
        pump(app, lambda: bool(tray.store.text(retry)))
        pump(app, lambda: tray._retry_job_path is None)
        assert tray._last_text == "Fresh dictation"
        tray.text_inserter.copy_text.assert_not_called()
        pump(app, lambda: not tray._retry_thread.isRunning()
             and not tray._worker_thread.isRunning())
        app.processEvents()


def test_new_recording_prevents_late_paste_from_older_job(controller):
    app, tray = controller
    tray._paste_targets["older recording"] = 123
    tray.on_hotkey_pressed()
    assert "older recording" not in tray._paste_targets


def test_failed_paste_keeps_full_text_on_disk(controller, tmp_path):
    app, tray = controller
    path = wav(tmp_path / "recording_paste.wav", seconds=90)
    tray._active_job_path = path
    tray._paste_targets[str(path)] = 123
    tray.text_inserter.insert_text.side_effect = RuntimeError("clipboard locked")
    paragraph = "A long instruction that must survive. " * 100
    tray._on_transcription_finished(TranscriptionResult(text=paragraph))
    assert DictationStore(tmp_path).text(path) == paragraph.strip()


def test_recovery_transcript_is_not_pasted_again_after_live_phrases(controller, tmp_path):
    app, tray = controller
    path = wav(tmp_path / "recording_live_fallback.wav")
    tray._active_job_path = path
    tray._indicator_job_path = path
    tray._paste_targets[str(path)] = 123
    tray._live_partial_paths.add(str(path))

    tray._on_transcription_finished(TranscriptionResult(text="Final fallback transcript"), path)

    tray.text_inserter.insert_text.assert_not_called()
    tray.text_inserter.type_text.assert_not_called()
    assert tray.store.text(path) == "Final fallback transcript"


def test_live_result_is_read_from_worker_before_queued_completion_signal(controller, tmp_path):
    from types import SimpleNamespace
    from whisperapp.live_transcription import LiveTranscriptionResult

    _app, tray = controller
    path = wav(tmp_path / "recording_live_finish.wav")
    tray._live_pending_path = path
    tray._live_inserted = True
    tray._live_typed_phrases = ["Live phrase"]
    tray._live_worker = SimpleNamespace(
        isRunning=lambda: False,
        result=LiveTranscriptionResult(text="Live phrase"),
    )

    tray._complete_live_capture(path)

    assert tray.store.text(path) == "Live phrase"
    tray.text_inserter.insert_text.assert_not_called()


def test_focus_change_saves_text_without_pasting_into_wrong_window(controller, tmp_path):
    app, tray = controller
    path = wav(tmp_path / "recording_focus.wav")
    tray._active_job_path = path
    tray._paste_targets[str(path)] = 123
    tray.text_inserter.foreground_window.return_value = 456
    tray._on_transcription_finished(TranscriptionResult(text="Keep out of the wrong application"))
    tray.text_inserter.insert_text.assert_not_called()
    assert tray.store.text(path) == "Keep out of the wrong application"


def test_history_exposes_persisted_text_and_retry(controller, tmp_path):
    app, tray = controller
    from whisperapp.history_dialog import HistoryDialog
    path = wav(tmp_path / "recording_visible.wav")
    tray.store.complete(path, "Previously lost paragraph")
    dialog = HistoryDialog(tray.store)
    try:
        assert dialog.entries.count() == 1
        assert dialog.detail.toPlainText() == "Previously lost paragraph"
        assert dialog.copy_button.isEnabled()
        assert not dialog.retry_button.isEnabled()
    finally:
        dialog.close()


def test_process_kill_during_recording_preserves_captured_audio(tmp_path):
    # Real file writes from the real recorder; only the microphone is simulated.
    script = '''
import sys,time
from pathlib import Path
from whisperapp import audio_recorder as ar
from tests.conftest import FakePyAudioModule
ar.pyaudio=FakePyAudioModule(read_delay=0.005)
ar._prepare_recordings_dir=lambda:Path(sys.argv[1])
ar._migrate_legacy_recordings=lambda directory:None
recorder=ar.AudioRecorder()
recorder.start_recording()
time.sleep(.15)
print(recorder.output_path,flush=True)
time.sleep(60)
'''
    process = subprocess.Popen([sys.executable, "-c", script, str(tmp_path)], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        path = Path(process.stdout.readline().strip())
        process.kill()
        process.wait(timeout=5)
        store = DictationStore(tmp_path)
        store.recover()
        with wave.open(str(path), "rb") as recording:
            assert recording.getnframes() > 0
            assert len(recording.readframes(recording.getnframes())) == recording.getnframes() * 2
        assert store.next_job()["path"] == str(path)
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_dictation_store_sanitizes_live_transcribe_model(tmp_path):
    path = wav(tmp_path / "recording_legacy_live.wav")
    store = DictationStore(tmp_path)
    store.update(path, state="transcribing", model="gpt-live-transcribe")
    # Reading should map gpt-live-transcribe to DEFAULT_TRANSCRIPTION_MODEL
    assert store.read(path)["model"] == "gpt-transcribe"
    store.recover()
    job = store.next_job()
    assert job is not None
    assert job["model"] == "gpt-transcribe"

