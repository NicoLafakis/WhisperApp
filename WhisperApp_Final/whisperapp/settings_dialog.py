from __future__ import annotations

from typing import Dict, List, Tuple

from PyQt5.QtWidgets import (
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

from whisperapp.transcription_service import TranscriptionService


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

        self.setWindowTitle("WhisperApp Settings")
        self.setMinimumWidth(440)

        self.api_key_input = QLineEdit(str(settings.get("api_key", "")))
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")

        self.model_combo = QComboBox()
        self.model_combo.addItems(["whisper-1"])
        self.model_combo.setCurrentText(str(settings.get("model", "whisper-1")))

        self.language_combo = QComboBox()
        for label, value in LANGUAGE_OPTIONS:
            self.language_combo.addItem(label, value)
        current_language = str(settings.get("language", "en"))
        for idx in range(self.language_combo.count()):
            if self.language_combo.itemData(idx) == current_language:
                self.language_combo.setCurrentIndex(idx)
                break

        self.hotkey_input = QLineEdit(str(settings.get("hotkey", "ctrl+shift+space")))
        self.hotkey_input.setReadOnly(True)

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

        form.addRow("", QLabel("Hotkey customization coming soon."))
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
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "API Key Error", "Please enter an API key.")
            return

        self.test_button.setEnabled(False)
        self.test_button.setText("Testing...")
        try:
            self._service.test_api_key(api_key)
            QMessageBox.information(self, "API Key Valid", "API key is valid.")
        except Exception as exc:
            QMessageBox.critical(self, "API Key Error", str(exc))
        finally:
            self.test_button.setEnabled(True)
            self.test_button.setText("Test API Key")

    def get_settings(self) -> Dict[str, object]:
        return {
            "api_key": self.api_key_input.text().strip(),
            "model": self.model_combo.currentText(),
            "language": self.language_combo.currentData(),
            "hotkey": self.hotkey_input.text().strip(),
            "auto_copy": self.auto_copy_checkbox.isChecked(),
            "show_notifications": self.show_notifications_checkbox.isChecked(),
        }
