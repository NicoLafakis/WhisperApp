import threading
import time
from unittest.mock import MagicMock

from PyQt5.QtWidgets import QApplication

from whisperapp import main
from whisperapp.transcription_service import TranscriptionResult


def test_hotkey_thread_to_recording_to_worker_to_output(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    config = MagicMock()
    config.get_settings.return_value = {"api_key": "test", "model": "gpt-transcribe"}
    recorder = MagicMock()
    recorder.recordings_dir = tmp_path
    service = MagicMock()
    service.transcribe.return_value = TranscriptionResult(text="Dictation reached the text field")
    inserter = MagicMock()
    for name, value in (("ConfigManager", config), ("AudioRecorder", recorder),
                        ("TranscriptionService", service), ("TextInserter", inserter)):
        monkeypatch.setattr(main, name, MagicMock(return_value=value))
    monkeypatch.setattr(main, "HotkeyListener", MagicMock())
    monkeypatch.setattr(main, "RecordingIndicator", MagicMock())
    monkeypatch.setattr(main, "QSystemTrayIcon", MagicMock())
    controller = main.WhisperTrayApp(app)
    callbacks = main.HotkeyListener.call_args.kwargs
    ui_thread = threading.get_ident()
    recorder.start_recording.side_effect = lambda: assert_ui_thread(ui_thread)

    try:
        for take in range(3):
            audio = tmp_path / f"recording_{take}.wav"
            audio.write_bytes(b"recorded audio")
            recorder.stop_recording.return_value = audio
            press = threading.Thread(target=callbacks["on_start"])
            press.start()
            press.join()
            app.processEvents()
            assert controller._is_recording
            release = threading.Thread(target=callbacks["on_stop"])
            release.start()
            release.join()
            deadline = time.monotonic() + 3
            while inserter.insert_text.call_count <= take and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(0.005)
            assert inserter.insert_text.call_count == take + 1
            assert not controller._is_recording
            assert not controller._is_transcribing
            assert controller._worker_thread.wait(1000)
        inserter.insert_text.assert_called_with(text="Dictation reached the text field", auto_copy=True)
    finally:
        controller.cleanup()
        app.aboutToQuit.disconnect(controller.cleanup)


def assert_ui_thread(expected):
    assert threading.get_ident() == expected
