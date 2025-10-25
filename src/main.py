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
from hotkey_manager import HotkeyManager
from window_manager import WindowManager
from command_parser import CommandParser
from voice_command_listener import VoiceCommandListener


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
        self.hotkey_manager = HotkeyManager()
        self.window_manager = WindowManager()
        self.command_parser = CommandParser()
        self.voice_listener = None

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

        # Start voice commands if enabled
        if self.config_manager.is_voice_commands_enabled():
            self.start_voice_commands()

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

        # Voice commands toggle action
        self.voice_commands_action = menu.addAction("Enable Voice Commands")
        self.voice_commands_action.setCheckable(True)
        self.voice_commands_action.setChecked(self.config_manager.is_voice_commands_enabled())
        self.voice_commands_action.triggered.connect(self.on_voice_commands_menu_toggled)

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

    def on_voice_commands_menu_toggled(self, checked):
        """Handle voice commands menu toggle"""
        self.config_manager.set_voice_command_setting('enabled', checked)

        if checked:
            self.voice_commands_action.setText("Disable Voice Commands")
            self.start_voice_commands()
        else:
            self.voice_commands_action.setText("Enable Voice Commands")
            self.stop_voice_commands()

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
        # Get hotkey from new hotkeys structure, fallback to legacy hotkey config
        hotkey = self.config_manager.get_hotkey('push_to_talk')
        if not hotkey:
            hotkey = self.config_manager.get('hotkey', 'ctrl+shift+space')

        try:
            # Register push-to-talk hotkey
            self.hotkey_manager.register_push_to_talk(
                hotkey,
                self.on_push_to_talk_press,
                self.on_push_to_talk_release
            )

            # Register voice command toggle hotkey
            voice_cmd_hotkey = self.config_manager.get_hotkey('toggle_voice_commands')
            if voice_cmd_hotkey:
                self.hotkey_manager.register_hotkey(
                    voice_cmd_hotkey,
                    self.toggle_voice_commands
                )

        except Exception as e:
            print(f"Error setting up hotkeys: {e}")

    def on_push_to_talk_press(self):
        """Handle push-to-talk press - start recording"""
        if not self.is_recording:
            self.start_recording()

    def on_push_to_talk_release(self):
        """Handle push-to-talk release - stop recording"""
        if self.is_recording:
            self.stop_recording()

    def toggle_voice_commands(self):
        """Toggle voice commands on/off"""
        current_state = self.config_manager.is_voice_commands_enabled()
        new_state = not current_state
        self.config_manager.set_voice_command_setting('enabled', new_state)

        if new_state:
            self.start_voice_commands()
        else:
            self.stop_voice_commands()

    def start_voice_commands(self):
        """Start voice command listening"""
        if self.voice_listener and self.voice_listener.is_active():
            return  # Already running

        try:
            # Get settings
            sensitivity = self.config_manager.get_voice_command_setting('sensitivity', 'medium')
            language = self.config_manager.get('language', 'en')

            # Map language code to speech recognition format
            lang_map = {
                'en': 'en-US',
                'es': 'es-ES',
                'fr': 'fr-FR',
                'de': 'de-DE',
                'it': 'it-IT',
                'pt': 'pt-PT',
                'ru': 'ru-RU',
                'ja': 'ja-JP',
                'ko': 'ko-KR',
                'zh': 'zh-CN',
            }
            sr_language = lang_map.get(language, 'en-US')

            # Create and start listener
            self.voice_listener = VoiceCommandListener(sensitivity, sr_language)
            self.voice_listener.command_detected.connect(self.on_voice_command_detected)
            self.voice_listener.error_occurred.connect(self.on_voice_command_error)
            self.voice_listener.status_changed.connect(self.on_voice_command_status)
            self.voice_listener.start()

            self.show_notification(
                "Voice Commands Enabled",
                "Voice navigation is now active"
            )

        except Exception as e:
            print(f"Error starting voice commands: {e}")
            self.show_notification(
                "Voice Command Error",
                f"Failed to start: {e}"
            )

    def stop_voice_commands(self):
        """Stop voice command listening"""
        if self.voice_listener:
            self.voice_listener.stop_listening()
            self.voice_listener.wait(2000)  # Wait up to 2 seconds for thread to finish
            self.voice_listener = None

        self.show_notification(
            "Voice Commands Disabled",
            "Voice navigation is now inactive"
        )

    def on_voice_command_detected(self, text: str):
        """Handle detected voice command"""
        print(f"Voice command detected: {text}")

        # Parse the command
        command = self.command_parser.parse(text)

        if not command:
            # Not a valid command
            print(f"Not a recognized command: {text}")
            return

        # Validate command
        monitor_count = self.window_manager.get_monitor_count()
        is_valid, error = self.command_parser.validate_command(command, monitor_count)

        if not is_valid:
            print(f"Invalid command: {error}")
            if self.config_manager.get_voice_command_setting('show_notifications', True):
                self.show_notification("Invalid Command", error)
            return

        # Execute command
        success = self.execute_voice_command(command)

        # Show notification if enabled
        if success and self.config_manager.get_voice_command_setting('show_notifications', True):
            self.show_notification(
                "Command Executed",
                f"Moved window to monitor {command.monitor}, quadrant {command.quadrant}"
            )

    def execute_voice_command(self, command) -> bool:
        """Execute a parsed voice command"""
        try:
            if command.action == 'move_window':
                # Move the active window to the specified position
                success = self.window_manager.move_window_to_quadrant(
                    command.monitor,
                    command.quadrant
                )
                return success
            else:
                print(f"Unknown command action: {command.action}")
                return False

        except Exception as e:
            print(f"Error executing command: {e}")
            self.show_notification("Command Error", f"Failed to execute: {e}")
            return False

    def on_voice_command_error(self, error_msg: str):
        """Handle voice command error"""
        print(f"Voice command error: {error_msg}")
        # Only show critical errors to user
        if "microphone" in error_msg.lower() or "service" in error_msg.lower():
            self.show_notification("Voice Command Error", error_msg)

    def on_voice_command_status(self, status: str):
        """Handle voice command status change"""
        print(f"Voice command status: {status}")

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

        # Re-register hotkeys if they changed
        self.hotkey_manager.unregister_all()
        self.setup_hotkeys()

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
        # Stop voice commands if running
        if self.voice_listener:
            self.stop_voice_commands()

        self.audio_recorder.cleanup()
        self.recording_indicator.hide_indicator()
        self.hotkey_manager.unregister_all()
        self.tray_icon.hide()
        self.quit()


def main():
    """Main entry point"""
    app = WhisperApp(sys.argv)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
