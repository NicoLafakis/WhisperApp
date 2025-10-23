"""
Settings dialog for WhisperApp
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QComboBox, QCheckBox,
                              QGroupBox, QFormLayout, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal


class SettingsDialog(QDialog):
    """Settings dialog window"""

    settings_changed = pyqtSignal(dict)  # Signal emitted when settings change

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialize the user interface"""
        self.setWindowTitle('WhisperApp Settings')
        self.setMinimumWidth(500)
        self.setModal(True)

        layout = QVBoxLayout()

        # API Settings Group
        api_group = QGroupBox("OpenAI API Settings")
        api_layout = QFormLayout()

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("sk-...")
        api_layout.addRow("API Key:", self.api_key_input)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["whisper-1"])
        api_layout.addRow("Model:", self.model_combo)

        self.language_combo = QComboBox()
        languages = [
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
        for name, code in languages:
            self.language_combo.addItem(name, code)
        api_layout.addRow("Language:", self.language_combo)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # Hotkey Settings Group
        hotkey_group = QGroupBox("Hotkey Settings")
        hotkey_layout = QFormLayout()

        self.hotkey_input = QLineEdit()
        self.hotkey_input.setPlaceholderText("e.g., ctrl+shift+space")
        self.hotkey_input.setReadOnly(True)
        hotkey_layout.addRow("Push-to-Talk:", self.hotkey_input)

        hotkey_note = QLabel("Note: Hotkey customization coming soon. Using default: Ctrl+Shift+Space")
        hotkey_note.setWordWrap(True)
        hotkey_note.setStyleSheet("color: gray; font-size: 9pt;")
        hotkey_layout.addRow(hotkey_note)

        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)

        # Behavior Settings Group
        behavior_group = QGroupBox("Behavior Settings")
        behavior_layout = QVBoxLayout()

        self.auto_copy_check = QCheckBox("Automatically copy to clipboard")
        self.auto_copy_check.setToolTip("Always copy transcription to clipboard")
        behavior_layout.addWidget(self.auto_copy_check)

        self.show_notifications_check = QCheckBox("Show notifications")
        self.show_notifications_check.setToolTip("Show notification when transcription is complete")
        behavior_layout.addWidget(self.show_notifications_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        test_btn = QPushButton("Test API Key")
        test_btn.clicked.connect(self.test_api_key)
        button_layout.addWidget(test_btn)

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_settings)
        save_btn.setDefault(True)
        button_layout.addWidget(save_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def load_settings(self):
        """Load settings from config manager"""
        self.api_key_input.setText(self.config_manager.get('api_key', ''))
        self.model_combo.setCurrentText(self.config_manager.get('model', 'whisper-1'))

        # Set language
        language = self.config_manager.get('language', 'en')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == language:
                self.language_combo.setCurrentIndex(i)
                break

        self.hotkey_input.setText(self.config_manager.get('hotkey', 'ctrl+shift+space'))
        self.auto_copy_check.setChecked(self.config_manager.get('auto_copy', True))
        self.show_notifications_check.setChecked(self.config_manager.get('show_notifications', True))

    def save_settings(self):
        """Save settings to config manager"""
        api_key = self.api_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Missing API Key",
                                "Please enter your OpenAI API key.")
            return

        # Save all settings
        self.config_manager.set('api_key', api_key)
        self.config_manager.set('model', self.model_combo.currentText())
        self.config_manager.set('language', self.language_combo.currentData())
        self.config_manager.set('hotkey', self.hotkey_input.text())
        self.config_manager.set('auto_copy', self.auto_copy_check.isChecked())
        self.config_manager.set('show_notifications', self.show_notifications_check.isChecked())

        # Emit signal with new settings
        self.settings_changed.emit(self.config_manager.config)

        QMessageBox.information(self, "Settings Saved",
                                "Your settings have been saved successfully!")
        self.accept()

    def test_api_key(self):
        """Test the API key"""
        api_key = self.api_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Missing API Key",
                                "Please enter an API key to test.")
            return

        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)

            # Test by listing models
            client.models.list()

            QMessageBox.information(self, "API Key Valid",
                                    "Your API key is valid and working!")
        except Exception as e:
            QMessageBox.critical(self, "API Key Error",
                                 f"API key test failed:\n{str(e)}")
