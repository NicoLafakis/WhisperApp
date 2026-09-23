import threading
import time

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QApplication, QMessageBox

from whisperapp.settings_dialog import SettingsDialog
from whisperapp.transcription_service import TranscriptionResult, TranscriptionErrorKind


_APP = None


def app():
    global _APP
    _APP = QApplication.instance() or QApplication([])
    return _APP


def spin_until(predicate, timeout=2):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline and not predicate():
        app().processEvents()
        time.sleep(0.005)
    app().processEvents()
    assert predicate()


class Service:
    def __init__(self, result=None, gate=None):
        self.result = result or TranscriptionResult(message="ok")
        self.gate = gate
        self.calls = 0

    def test_api_key(self, api_key, model):
        self.calls += 1
        if self.gate:
            self.gate.wait(2)
        return self.result


def test_api_key_check_runs_in_worker_and_restores_ui(monkeypatch):
    app()
    gate = threading.Event()
    service = Service(gate=gate)
    dialog = SettingsDialog({"api_key": "sk-test"}, service)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    dialog._test_api_key()
    assert not dialog.test_button.isEnabled()
    event_processed = []
    QTimer.singleShot(0, lambda: event_processed.append(True))
    app().processEvents()
    assert event_processed == [True]
    gate.set()
    spin_until(lambda: dialog._check_thread is None)
    assert dialog.test_button.isEnabled()
    assert dialog.test_button.text() == "Test API Key"
    assert QApplication.overrideCursor() is None
    dialog.close()


def test_api_key_failure_shows_actionable_message_and_restores_ui(monkeypatch):
    app()
    service = Service(TranscriptionResult(error_kind=TranscriptionErrorKind.AUTH_FAILED, message="key rejected"))
    dialog = SettingsDialog({"api_key": "sk-test"}, service)
    shown = []
    monkeypatch.setattr(QMessageBox, "critical", lambda *args: shown.append(args[-1]))
    dialog._test_api_key()
    spin_until(lambda: dialog._check_thread is None)
    assert shown == ["key rejected"]
    assert dialog.test_button.isEnabled()
    assert QApplication.overrideCursor() is None
    dialog.close()


def test_closing_dialog_keeps_worker_alive_without_crashing(monkeypatch):
    app()
    gate = threading.Event()
    service = Service(gate=gate)
    dialog = SettingsDialog({"api_key": "sk-test"}, service)
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    dialog._test_api_key()
    thread = dialog._check_thread
    dialog.reject()
    assert thread.isRunning()
    assert QApplication.overrideCursor() is None
    gate.set()
    spin_until(lambda: not thread.isRunning())
    assert thread not in __import__("whisperapp.settings_dialog", fromlist=["_ACTIVE_CHECK_THREADS"])._ACTIVE_CHECK_THREADS


def test_api_key_check_does_not_start_a_duplicate_worker(monkeypatch):
    app()
    monkeypatch.setattr(QMessageBox, "information", lambda *args: None)
    gate = threading.Event()
    service = Service(gate=gate)
    dialog = SettingsDialog({"api_key": "sk-test"}, service)
    dialog._test_api_key()
    thread = dialog._check_thread
    dialog._test_api_key()
    assert dialog._check_thread is thread
    gate.set()
    spin_until(lambda: dialog._check_thread is None)
    assert service.calls == 1
    dialog.close()
