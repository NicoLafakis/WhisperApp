from __future__ import annotations

import logging
import threading
from typing import Dict, List, Tuple

from PyQt5.QtCore import QObject, QThread, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from whisperapp.audio_recorder import AudioRecorder
from whisperapp.config_manager import DEFAULT_TRANSCRIPTION_MODEL
from whisperapp.transcription_service import (
    BILLING_URL,
    ERROR_HEADLINES,
    TranscriptionErrorKind,
    TranscriptionService,
)


logger = logging.getLogger(__name__)
_ACTIVE_CHECK_THREADS = set()
_ACTIVE_CHECK_LOCK = threading.Lock()


class _ApiKeyCheckWorker(QObject):
    completed = pyqtSignal(object)

    def __init__(self, service, api_key: str, model: str) -> None:
        super().__init__()
        self.service = service
        self.api_key = api_key
        self.model = model

    @pyqtSlot()
    def run(self) -> None:
        try:
            result = self.service.test_api_key(self.api_key, model=self.model)
        except Exception as exc:
            logger.exception("API key check worker failed")
            result = exc
        self.completed.emit(result)


LANGUAGE_OPTIONS: List[Tuple[str, str]] = [
    ("Auto Detect", ""),
    ("English", "en"),
    ("Spanish", "es"),
    ("French", "fr"),
    ("German", "de"),
    ("Italian", "it"),
    ("Portuguese", "pt"),
    ("Russian", "ru"),
    ("Japanese", "ja"),
    ("Korean", "ko"),
    ("Chinese", "zh"),
]


class SettingsDialog(QDialog):
    def __init__(
        self,
        settings: Dict[str, object],
        transcription_service: TranscriptionService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._service = transcription_service
        self._settings = settings
        self._check_thread = None
        self._check_worker = None
        self._cursor_overridden = False
        self._closing = False

        self.setWindowTitle("WhisperApp Settings")
        self.setMinimumWidth(440)

        self.api_key_input = QLineEdit(str(settings.get("api_key", "")))
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")

        self.model_combo = QComboBox()
        self.model_combo.addItems([DEFAULT_TRANSCRIPTION_MODEL, "whisper-1"])
        current_model = str(settings.get("model", DEFAULT_TRANSCRIPTION_MODEL))
        if self.model_combo.findText(current_model) < 0:
            self.model_combo.addItem(current_model)
        self.model_combo.setCurrentText(current_model)
        self.model_combo.setToolTip(
            "GPT Transcribe is recommended for dictation. "
            "Whisper is a legacy fallback scheduled to retire February 26, 2027."
        )

        self.language_combo = QComboBox()
        for label, value in LANGUAGE_OPTIONS:
            self.language_combo.addItem(label, value)
        current_language = str(settings.get("language", "en"))
        for idx in range(self.language_combo.count()):
            if self.language_combo.itemData(idx) == current_language:
                self.language_combo.setCurrentIndex(idx)
                break

        # Hotkey field — editable with validation
        self.hotkey_input = QLineEdit(str(settings.get("hotkey", "ctrl+shift+space")))
        self.hotkey_input.setPlaceholderText("e.g. ctrl+shift+space")

        # Audio device selector
        self.audio_device_combo = QComboBox()
        self.audio_device_combo.addItem("Default", "default")
        try:
            for idx, name in AudioRecorder.list_input_devices():
                display = f"{name}"
                self.audio_device_combo.addItem(display, str(idx))
        except Exception:
            # No enumerable input devices: the "Default" entry alone still works.
            logger.warning("Could not enumerate input devices", exc_info=True)

        current_device = str(settings.get("audio_device", "default"))
        for idx in range(self.audio_device_combo.count()):
            if str(self.audio_device_combo.itemData(idx)) == current_device:
                self.audio_device_combo.setCurrentIndex(idx)
                break

        self.auto_copy_checkbox = QCheckBox()
        self.auto_copy_checkbox.setChecked(bool(settings.get("auto_copy", True)))

        self.show_notifications_checkbox = QCheckBox()
        self.show_notifications_checkbox.setChecked(
            bool(settings.get("show_notifications", True))
        )

        self.test_button = QPushButton("Test API Key")
        self.test_button.clicked.connect(self._test_api_key)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.accept)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)

        form = QFormLayout()
        form.addRow("OpenAI API Key", self.api_key_input)
        form.addRow("Model", self.model_combo)
        form.addRow("Language", self.language_combo)
        form.addRow("Hotkey", self.hotkey_input)
        form.addRow("Microphone", self.audio_device_combo)
        form.addRow("Automatically copy to clipboard", self.auto_copy_checkbox)
        form.addRow("Show notifications", self.show_notifications_checkbox)

        actions = QHBoxLayout()
        actions.addWidget(self.test_button)
        actions.addStretch(1)
        actions.addWidget(self.save_button)
        actions.addWidget(self.cancel_button)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addSpacing(8)
        layout.addLayout(actions)

    def _test_api_key(self) -> None:
        if self._check_thread is not None:
            return
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "API Key Error", "Please enter an API key.")
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("Testing...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        self._cursor_overridden = True
        thread = QThread()
        worker = _ApiKeyCheckWorker(self._service, api_key, self.model_combo.currentText())
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(self._api_key_check_completed)
        worker.completed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(lambda t=thread: self._api_key_check_finished(t))
        self._check_thread = thread
        self._check_worker = worker
        with _ACTIVE_CHECK_LOCK:
            _ACTIVE_CHECK_THREADS.add(thread)
        thread.start()

    @pyqtSlot(object)
    def _api_key_check_completed(self, result) -> None:
        if self._cursor_overridden:
            QApplication.restoreOverrideCursor()
            self._cursor_overridden = False
        self.test_button.setEnabled(True)
        self.test_button.setText("Test API Key")
        if self._closing:
            return
        if isinstance(result, Exception):
            QMessageBox.critical(self, "API Key Error", "The API key check failed. See the application log for details.")
            return

        if result.ok:
            QMessageBox.information(
                self,
                "API Key Valid",
                "API key is valid and can transcribe audio.",
            )
            return

        # Show the API's own wording: the quota body names the billing page, and a
        # generic "invalid key" here is what sent the last investigation the wrong way.
        title = ERROR_HEADLINES.get(result.error_kind, "API Key Error")
        detail = result.message.strip() or "The API key check failed."
        if result.error_kind is TranscriptionErrorKind.QUOTA_EXHAUSTED:
            detail = f"{detail}\n\nAdd credits at:\n{BILLING_URL}"
        QMessageBox.critical(self, title, detail)

    def closeEvent(self, event) -> None:
        self._closing = True
        self._restore_wait_cursor()
        super().closeEvent(event)

    def done(self, result: int) -> None:
        self._closing = True
        self._restore_wait_cursor()
        super().done(result)

    def _restore_wait_cursor(self) -> None:
        if self._cursor_overridden:
            QApplication.restoreOverrideCursor()
            self._cursor_overridden = False

    def _api_key_check_finished(self, thread) -> None:
        with _ACTIVE_CHECK_LOCK:
            _ACTIVE_CHECK_THREADS.discard(thread)
        if self._check_thread is thread:
            self._check_thread = None
            self._check_worker = None

    def get_settings(self) -> Dict[str, object]:
        return {
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_combo.currentText(),
            "language": self.language_combo.currentData(),
            "hotkey": self.hotkey_input.text().strip(),
            "audio_device": self.audio_device_combo.currentData(),
            "auto_copy": self.auto_copy_checkbox.isChecked(),
            "show_notifications": self.show_notifications_checkbox.isChecked(),
        }
