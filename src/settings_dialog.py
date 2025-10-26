"""
Settings dialog for WhisperApp
"""
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                              QLineEdit, QPushButton, QComboBox, QCheckBox,
                              QGroupBox, QFormLayout, QMessageBox, QTabWidget,
                              QWidget, QTextEdit)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QKeySequence
import keyboard


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
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.setModal(True)

        layout = QVBoxLayout()

        # Create tab widget
        self.tabs = QTabWidget()

        # Create tabs
        self.tabs.addTab(self.create_api_tab(), "API Settings")
        self.tabs.addTab(self.create_hotkeys_tab(), "Hotkeys")
        self.tabs.addTab(self.create_voice_commands_tab(), "Voice Commands")
        self.tabs.addTab(self.create_behavior_tab(), "Behavior")

        layout.addWidget(self.tabs)

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

    def create_api_tab(self):
        """Create API settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()

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
        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def create_hotkeys_tab(self):
        """Create hotkeys settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Push-to-Talk Hotkey
        ptt_group = QGroupBox("Push-to-Talk Hotkey")
        ptt_layout = QVBoxLayout()

        ptt_form = QFormLayout()
        self.ptt_hotkey_input = QLineEdit()
        self.ptt_hotkey_input.setPlaceholderText("e.g., ctrl+shift+space")
        ptt_form.addRow("Hotkey:", self.ptt_hotkey_input)

        self.ptt_record_btn = QPushButton("Record Hotkey")
        self.ptt_record_btn.clicked.connect(lambda: self.record_hotkey('ptt'))
        ptt_form.addRow("", self.ptt_record_btn)

        ptt_layout.addLayout(ptt_form)

        ptt_help = QLabel("Press and hold the key combination you want to use.\n"
                         "Example: ctrl+shift+space")
        ptt_help.setWordWrap(True)
        ptt_help.setStyleSheet("color: gray; font-size: 9pt;")
        ptt_layout.addWidget(ptt_help)

        ptt_group.setLayout(ptt_layout)
        layout.addWidget(ptt_group)

        # Voice Command Toggle Hotkey
        vc_group = QGroupBox("Voice Command Toggle Hotkey")
        vc_layout = QVBoxLayout()

        vc_form = QFormLayout()
        self.vc_hotkey_input = QLineEdit()
        self.vc_hotkey_input.setPlaceholderText("e.g., ctrl+shift+v")
        vc_form.addRow("Hotkey:", self.vc_hotkey_input)

        self.vc_record_btn = QPushButton("Record Hotkey")
        self.vc_record_btn.clicked.connect(lambda: self.record_hotkey('vc'))
        vc_form.addRow("", self.vc_record_btn)

        vc_layout.addLayout(vc_form)

        vc_help = QLabel("This hotkey toggles voice navigation on/off.\n"
                        "Example: ctrl+shift+v")
        vc_help.setWordWrap(True)
        vc_help.setStyleSheet("color: gray; font-size: 9pt;")
        vc_layout.addWidget(vc_help)

        vc_group.setLayout(vc_layout)
        layout.addWidget(vc_group)

        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def create_voice_commands_tab(self):
        """Create voice commands settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        # Enable/Disable
        enable_group = QGroupBox("Voice Navigation")
        enable_layout = QVBoxLayout()

        self.voice_commands_enabled_check = QCheckBox("Enable voice navigation")
        self.voice_commands_enabled_check.setToolTip(
            "Allow voice commands to control window positioning"
        )
        enable_layout.addWidget(self.voice_commands_enabled_check)

        enable_group.setLayout(enable_layout)
        layout.addWidget(enable_group)

        # Settings
        settings_group = QGroupBox("Voice Command Settings")
        settings_layout = QFormLayout()

        self.vc_notifications_check = QCheckBox("Show notifications for voice commands")
        settings_layout.addRow(self.vc_notifications_check)

        self.vc_sensitivity_combo = QComboBox()
        self.vc_sensitivity_combo.addItems(["Low", "Medium", "High"])
        settings_layout.addRow("Sensitivity:", self.vc_sensitivity_combo)

        settings_group.setLayout(settings_layout)
        layout.addWidget(settings_group)

        # Available commands
        commands_group = QGroupBox("Available Commands")
        commands_layout = QVBoxLayout()

        commands_text = QTextEdit()
        commands_text.setReadOnly(True)
        commands_text.setMaximumHeight(200)
        commands_text.setPlainText(
            "Voice navigation commands:\n\n"
            "• 'Monitor [1-9], quadrant [1-4]'\n"
            "  Example: 'Monitor one, quadrant one'\n"
            "  Moves active window to specified monitor and quadrant\n\n"
            "Quadrant layout:\n"
            "  +-----+-----+\n"
            "  |  1  |  2  |\n"
            "  +-----+-----+\n"
            "  |  3  |  4  |\n"
            "  +-----+-----+"
        )
        commands_layout.addWidget(commands_text)

        commands_group.setLayout(commands_layout)
        layout.addWidget(commands_group)

        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def create_behavior_tab(self):
        """Create behavior settings tab"""
        tab = QWidget()
        layout = QVBoxLayout()

        behavior_group = QGroupBox("General Behavior")
        behavior_layout = QVBoxLayout()

        self.auto_copy_check = QCheckBox("Automatically copy transcription to clipboard")
        self.auto_copy_check.setToolTip("Always copy transcription to clipboard")
        behavior_layout.addWidget(self.auto_copy_check)

        self.show_notifications_check = QCheckBox("Show transcription notifications")
        self.show_notifications_check.setToolTip("Show notification when transcription is complete")
        behavior_layout.addWidget(self.show_notifications_check)

        behavior_group.setLayout(behavior_layout)
        layout.addWidget(behavior_group)

        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def record_hotkey(self, hotkey_type):
        """Record a hotkey combination"""
        if hotkey_type == 'ptt':
            input_field = self.ptt_hotkey_input
            button = self.ptt_record_btn
            label = "Push-to-Talk"
        else:
            input_field = self.vc_hotkey_input
            button = self.vc_record_btn
            label = "Voice Command Toggle"

        button.setText("Press keys...")
        button.setEnabled(False)

        # Create a simple key recorder
        recorded_keys = []

        def on_key_event(event):
            if event.event_type == 'down' and event.name not in recorded_keys:
                recorded_keys.append(event.name)
                # Update the input field
                hotkey_str = '+'.join(recorded_keys)
                input_field.setText(hotkey_str)

        # Hook keyboard temporarily
        hook = keyboard.hook(on_key_event)

        # Use a timer to stop recording after a short delay
        from PyQt5.QtCore import QTimer
        timer = QTimer()

        def stop_recording():
            keyboard.unhook(hook)
            button.setText("Record Hotkey")
            button.setEnabled(True)
            if recorded_keys:
                # Validate the hotkey
                from hotkey_manager import HotkeyManager
                hm = HotkeyManager()
                is_valid, error = hm.validate_hotkey('+'.join(recorded_keys))
                if not is_valid:
                    QMessageBox.warning(self, "Invalid Hotkey", error)
                    input_field.clear()

        timer.singleShot(3000, stop_recording)  # Stop after 3 seconds

    def load_settings(self):
        """Load settings from config manager"""
        # API Settings
        self.api_key_input.setText(self.config_manager.get('api_key', ''))
        self.model_combo.setCurrentText(self.config_manager.get('model', 'whisper-1'))

        # Set language
        language = self.config_manager.get('language', 'en')
        for i in range(self.language_combo.count()):
            if self.language_combo.itemData(i) == language:
                self.language_combo.setCurrentIndex(i)
                break

        # Hotkey Settings
        ptt_hotkey = self.config_manager.get_hotkey('push_to_talk')
        if not ptt_hotkey:
            ptt_hotkey = self.config_manager.get('hotkey', 'ctrl+shift+space')
        self.ptt_hotkey_input.setText(ptt_hotkey)

        vc_hotkey = self.config_manager.get_hotkey('toggle_voice_commands')
        if not vc_hotkey:
            vc_hotkey = 'ctrl+shift+v'
        self.vc_hotkey_input.setText(vc_hotkey)

        # Voice Command Settings
        self.voice_commands_enabled_check.setChecked(
            self.config_manager.is_voice_commands_enabled()
        )
        self.vc_notifications_check.setChecked(
            self.config_manager.get_voice_command_setting('show_notifications', True)
        )
        sensitivity = self.config_manager.get_voice_command_setting('sensitivity', 'medium')
        self.vc_sensitivity_combo.setCurrentText(sensitivity.capitalize())

        # Behavior Settings
        self.auto_copy_check.setChecked(self.config_manager.get('auto_copy', True))
        self.show_notifications_check.setChecked(self.config_manager.get('show_notifications', True))

    def save_settings(self):
        """Save settings to config manager"""
        api_key = self.api_key_input.text().strip()

        if not api_key:
            QMessageBox.warning(self, "Missing API Key",
                                "Please enter your OpenAI API key.")
            return

        # Validate hotkeys
        from hotkey_manager import HotkeyManager
        hm = HotkeyManager()

        ptt_hotkey = self.ptt_hotkey_input.text().strip()
        if ptt_hotkey:
            is_valid, error = hm.validate_hotkey(ptt_hotkey)
            if not is_valid:
                QMessageBox.warning(self, "Invalid Push-to-Talk Hotkey", error)
                return

        vc_hotkey = self.vc_hotkey_input.text().strip()
        if vc_hotkey:
            is_valid, error = hm.validate_hotkey(vc_hotkey)
            if not is_valid:
                QMessageBox.warning(self, "Invalid Voice Command Hotkey", error)
                return

        # Save API settings
        self.config_manager.set('api_key', api_key)
        self.config_manager.set('model', self.model_combo.currentText())
        self.config_manager.set('language', self.language_combo.currentData())

        # Save hotkey settings
        if ptt_hotkey:
            self.config_manager.set_hotkey('push_to_talk', ptt_hotkey)
            self.config_manager.set('hotkey', ptt_hotkey)  # Legacy support
        if vc_hotkey:
            self.config_manager.set_hotkey('toggle_voice_commands', vc_hotkey)

        # Save voice command settings
        self.config_manager.set_voice_command_setting(
            'enabled',
            self.voice_commands_enabled_check.isChecked()
        )
        self.config_manager.set_voice_command_setting(
            'show_notifications',
            self.vc_notifications_check.isChecked()
        )
        self.config_manager.set_voice_command_setting(
            'sensitivity',
            self.vc_sensitivity_combo.currentText().lower()
        )

        # Save behavior settings
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
            import httpx

            # Create httpx client without proxy to avoid compatibility issues
            http_client = httpx.Client(
                timeout=60.0,
                follow_redirects=True
            )
            client = OpenAI(api_key=api_key, http_client=http_client)

            # Test by listing models
            client.models.list()

            QMessageBox.information(self, "API Key Valid",
                                    "Your API key is valid and working!")
        except Exception as e:
            QMessageBox.critical(self, "API Key Error",
                                 f"API key test failed:\n{str(e)}")
