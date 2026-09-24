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
    recorder.start_recording.side_effect = lambda: assert_not_ui_thread(ui_thread)

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


def assert_not_ui_thread(expected):
    assert threading.get_ident() != expected


def test_hotkey_shows_starting_feedback_without_waiting_for_audio_device(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    config = MagicMock()
    config.get_settings.return_value = {"api_key": "test", "model": "gpt-transcribe"}
    recorder = MagicMock()
    recorder.recordings_dir = tmp_path
    entered = threading.Event()
    release = threading.Event()

    def slow_start():
        entered.set()
        release.wait(2)

    recorder.start_recording.side_effect = slow_start
    for name, value in (("ConfigManager", config), ("AudioRecorder", recorder),
                        ("TranscriptionService", MagicMock()), ("TextInserter", MagicMock())):
        monkeypatch.setattr(main, name, MagicMock(return_value=value))
    monkeypatch.setattr(main, "HotkeyListener", MagicMock())
    indicator = MagicMock()
    monkeypatch.setattr(main, "RecordingIndicator", MagicMock(return_value=indicator))
    monkeypatch.setattr(main, "QSystemTrayIcon", MagicMock())
    controller = main.WhisperTrayApp(app)
    try:
        started = time.monotonic()
        controller.on_hotkey_pressed()
        elapsed = time.monotonic() - started
        assert elapsed < 0.2
        assert entered.wait(1)
        indicator.show_indicator.assert_called_once()
        indicator.set_state.assert_called_with("STARTING")
        assert controller._is_recording
    finally:
        release.set()
        controller.cleanup()
        app.aboutToQuit.disconnect(controller.cleanup)


def test_release_during_startup_is_deferred_until_microphone_is_ready(monkeypatch, tmp_path):
    app = QApplication.instance() or QApplication([])
    config = MagicMock()
    config.get_settings.return_value = {"api_key": "test", "model": "gpt-transcribe"}
    recorder = MagicMock()
    recorder.recordings_dir = tmp_path
    entered = threading.Event()
    release = threading.Event()
    audio = tmp_path / "quick-take.wav"
    audio.write_bytes(b"audio")
    recorder.stop_recording.return_value = audio

    def slow_start():
        entered.set()
        release.wait(2)

    recorder.start_recording.side_effect = slow_start
    for name, value in (("ConfigManager", config), ("AudioRecorder", recorder),
                        ("TranscriptionService", MagicMock()), ("TextInserter", MagicMock())):
        monkeypatch.setattr(main, name, MagicMock(return_value=value))
    monkeypatch.setattr(main, "HotkeyListener", MagicMock())
    monkeypatch.setattr(main, "RecordingIndicator", MagicMock())
    monkeypatch.setattr(main, "QSystemTrayIcon", MagicMock())
    controller = main.WhisperTrayApp(app)
    try:
        controller.on_hotkey_pressed()
        assert entered.wait(1)
        controller.on_hotkey_released()
        assert recorder.stop_recording.call_count == 0
        release.set()
        deadline = time.monotonic() + 2
        while not recorder.stop_recording.called and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.005)
        assert recorder.stop_recording.called
    finally:
        release.set()
        controller.cleanup()
        app.aboutToQuit.disconnect(controller.cleanup)


def test_voice_modulator_responds_to_input_and_processing_stays_unobtrusive():
    app = QApplication.instance() or QApplication([])
    volume = [0.0]
    indicator = main.RecordingIndicator(lambda: volume[0])
    indicator.set_state("RECORDING")
    indicator._tick()
    silent_level = indicator._display_level
    silent_image = indicator.grab().toImage()
    volume[0] = 0.02
    for _ in range(4):
        indicator._tick()
    assert indicator._display_level > silent_level
    speaking_image = indicator.grab().toImage()
    for x in (187, 199, 211, 223, 235):
        assert speaking_image.pixelColor(x, 43).red() > silent_image.pixelColor(x, 43).red() + 100

    indicator.set_state("TRANSCRIBING")
    indicator.set_partial_text("A partial result")
    volume[0] = 0.0
    processing_image = indicator.grab().toImage()
    indicator._tick()
    assert indicator.grab().toImage() == processing_image
    assert indicator._state == "TRANSCRIBING"
    assert indicator._partial_text == "A partial result"


def test_new_processing_state_cancels_pending_terminal_hide():
    app = QApplication.instance() or QApplication([])
    indicator = main.RecordingIndicator(lambda: 0.0)
    indicator.finish("DONE", "Text inserted", 1500)
    assert indicator._hide_timer.isActive()
    indicator.set_state("TRANSCRIBING")
    assert not indicator._hide_timer.isActive()


def test_recording_indicator_is_compact_draggable_and_persists_position():
    from PyQt5.QtCore import QPoint, Qt

    app = QApplication.instance() or QApplication([])
    positions = []
    indicator = main.RecordingIndicator(on_position_changed=lambda x, y: positions.append((x, y)))
    indicator.show_indicator()
    app.processEvents()
    assert indicator.size().width() <= 270
    assert indicator.size().height() <= 64

    class MouseEvent:
        def __init__(self, global_pos, button=Qt.LeftButton):
            self._global_pos = global_pos
            self._button = button

        def button(self):
            return self._button

        def buttons(self):
            return Qt.LeftButton

        def globalPos(self):
            return self._global_pos

        def accept(self):
            pass

    press_pos = indicator.frameGeometry().topLeft() + QPoint(16, 16)
    move_pos = press_pos + QPoint(30, 30)
    indicator.mousePressEvent(MouseEvent(press_pos))
    indicator.mouseMoveEvent(MouseEvent(move_pos))
    indicator.mouseReleaseEvent(MouseEvent(move_pos))
    app.processEvents()
    assert positions
    assert positions[-1] == (indicator.x(), indicator.y())
    assert indicator._clamp_position(-1000, -1000, app.primaryScreen().availableGeometry()) == QPoint(
        app.primaryScreen().availableGeometry().left(), app.primaryScreen().availableGeometry().top()
    )
    indicator.close()
