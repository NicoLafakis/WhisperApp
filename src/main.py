"""
WhisperApp - Push-to-Talk Transcription Application
Main application file
"""
import sys
import os
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QMessageBox
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import QThread, pyqtSignal
import keyboard
from plyer import notification

from config_manager import ConfigManager
from audio_recorder import AudioRecorder
from transcription_service import TranscriptionService
from text_inserter import TextInserter
from settings_dialog import SettingsDialog
from recording_indicator import RecordingIndicator


class TranscriptionWorker(QThread):
    """Worker thread for transcription to avoid blocking UI"""

    finished = pyqtSignal(str)  # Emits transcribed text
    error = pyqtSignal(str)  # Emits error message

    def __init__(self, transcription_service, audio_file, model, language):
        super().__init__()
        self.transcription_service = transcription_service
        self.audio_file = audio_file
        self.model = model
        self.language = language

    def run(self):
        """Run transcription in background thread"""
        try:
            text = self.transcription_service.transcribe(
                self.audio_file,
                model=self.model,
                language=self.language if self.language else None
            )
            if text:
                self.finished.emit(text)
            else:
                self.error.emit("Transcription returned empty result")
        except Exception as e:
            self.error.emit(str(e))


class WhisperApp(QApplication):
    """Main application class"""

    def __init__(self, argv):
        super().__init__(argv)
        self.setQuitOnLastWindowClosed(False)

        # Initialize components
        self.config_manager = ConfigManager()
        self.audio_recorder = AudioRecorder()
        self.text_inserter = TextInserter()

        # Initialize transcription service with API key
        api_key = self.config_manager.get_api_key()
        if not api_key:
            # Try to get from environment variable
            api_key = os.getenv('WHISPER_API_KEY', '')
            if api_key:
                self.config_manager.set_api_key(api_key)

        self.transcription_service = TranscriptionService(api_key)

        # State
        self.is_recording = False
        self.transcription_worker = None

        # Setup UI
        self.setup_tray_icon()
        self.setup_hotkeys()

        # Initialize recording indicator
        self.recording_indicator = RecordingIndicator()

        # Show welcome message if API key not configured
        if not self.transcription_service.is_configured():
            self.show_welcome_message()

    def setup_tray_icon(self):
        """Setup system tray icon and menu"""
        # Create tray icon
        icon_path = self.get_icon_path()
        self.tray_icon = QSystemTrayIcon(QIcon(icon_path), self)

        # Create menu
        menu = QMenu()

        # Status action
        self.status_action = menu.addAction("Status: Ready")
        self.status_action.setEnabled(False)

        menu.addSeparator()

        # Settings action
        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.show_settings)

        # About action
        about_action = menu.addAction("About")
        about_action.triggered.connect(self.show_about)

        menu.addSeparator()

        # Quit action
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_app)

        self.tray_icon.setContextMenu(menu)
        self.tray_icon.show()

        # Show notification on startup
        self.tray_icon.showMessage(
            "WhisperApp Started",
            "Press Ctrl+Shift+Space to start transcription",
            QSystemTrayIcon.Information,
            2000
        )

    def get_icon_path(self):
        """Get path to application icon"""
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = Path(sys._MEIPASS)
        else:
            # Running as script
            base_path = Path(__file__).parent.parent

        icon_path = base_path / 'assets' / 'icon.png'
        if icon_path.exists():
            return str(icon_path)

        # Return empty icon if not found
        return ""

    def setup_hotkeys(self):
        """Setup global hotkeys"""
        hotkey = self.config_manager.get('hotkey', 'ctrl+shift+space')

        try:
            # Register hotkey for press and release
            keyboard.on_press_key('space', self.on_hotkey_press, suppress=False)
            keyboard.on_release_key('space', self.on_hotkey_release, suppress=False)
        except Exception as e:
            print(f"Error setting up hotkeys: {e}")

    def on_hotkey_press(self, event):
        """Handle hotkey press - start recording"""
        # Check if Ctrl+Shift are held
        if keyboard.is_pressed('ctrl') and keyboard.is_pressed('shift'):
            if not self.is_recording:
                self.start_recording()

    def on_hotkey_release(self, event):
        """Handle hotkey release - stop recording"""
        if self.is_recording:
            self.stop_recording()

    def start_recording(self):
        """Start recording audio"""
        if not self.transcription_service.is_configured():
            self.show_notification(
                "API Key Required",
                "Please configure your OpenAI API key in settings"
            )
            return

        self.is_recording = True
        self.status_action.setText("Status: Recording...")
        self.audio_recorder.start_recording()

        # Show recording indicator
        self.recording_indicator.show_recording()

        self.show_notification(
            "Recording Started",
            "Speak now... Release keys to transcribe"
        )

    def stop_recording(self):
        """Stop recording and start transcription"""
        if not self.is_recording:
            return

        self.is_recording = False
        self.status_action.setText("Status: Transcribing...")

        audio_file = self.audio_recorder.stop_recording()

        if not audio_file:
            self.status_action.setText("Status: Ready")
            self.show_notification("Error", "No audio recorded")
            # Hide indicator on error
            self.recording_indicator.hide_indicator()
            return

        # Update indicator to show transcribing status
        self.recording_indicator.show_transcribing()

        # Start transcription in background thread
        model = self.config_manager.get('model', 'whisper-1')
        language = self.config_manager.get('language', 'en')

        self.transcription_worker = TranscriptionWorker(
            self.transcription_service,
            audio_file,
            model,
            language
        )
        self.transcription_worker.finished.connect(self.on_transcription_complete)
        self.transcription_worker.error.connect(self.on_transcription_error)
        self.transcription_worker.start()

    def on_transcription_complete(self, text):
        """Handle completed transcription"""
        self.status_action.setText("Status: Ready")

        if not text:
            self.show_notification("Error", "No transcription result")
            # Hide indicator
            self.recording_indicator.hide_indicator()
            return

        # Insert text or copy to clipboard
        auto_copy = self.config_manager.get('auto_copy', True)

        if auto_copy:
            self.text_inserter.copy_to_clipboard(text)

        # Try to insert text (which also copies to clipboard)
        self.text_inserter.insert_text(text)

        # Hide indicator after text is inserted
        self.recording_indicator.hide_indicator()

        # Show notification
        if self.config_manager.get('show_notifications', True):
            self.show_notification(
                "Transcription Complete",
                f"Transcribed: {text[:50]}..." if len(text) > 50 else f"Transcribed: {text}"
            )

    def on_transcription_error(self, error_msg):
        """Handle transcription error"""
        self.status_action.setText("Status: Ready")
        # Hide indicator on error
        self.recording_indicator.hide_indicator()
        self.show_notification("Transcription Error", error_msg)

    def show_notification(self, title, message):
        """Show system notification"""
        try:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, 3000)
        except Exception as e:
            print(f"Notification error: {e}")

    def show_settings(self):
        """Show settings dialog"""
        dialog = SettingsDialog(self.config_manager)
        dialog.settings_changed.connect(self.on_settings_changed)
        dialog.exec_()

    def on_settings_changed(self, new_settings):
        """Handle settings changes"""
        # Update transcription service with new API key
        api_key = self.config_manager.get_api_key()
        self.transcription_service.update_api_key(api_key)

        self.show_notification("Settings Updated", "Your settings have been saved")

    def show_welcome_message(self):
        """Show welcome message on first run"""
        QMessageBox.information(
            None,
            "Welcome to WhisperApp",
            "Welcome to WhisperApp!\n\n"
            "To get started, please configure your OpenAI API key in Settings.\n\n"
            "Right-click the system tray icon to access settings."
        )

    def show_about(self):
        """Show about dialog"""
        QMessageBox.information(
            None,
            "About WhisperApp",
            "WhisperApp v1.0\n\n"
            "Push-to-Talk Transcription Application\n\n"
            "Powered by OpenAI Whisper\n\n"
            "Hotkey: Ctrl+Shift+Space"
        )

    def quit_app(self):
        """Quit the application"""
        self.audio_recorder.cleanup()
        self.recording_indicator.hide_indicator()
        self.tray_icon.hide()
        self.quit()


def main():
    """Main entry point"""
    app = WhisperApp(sys.argv)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
