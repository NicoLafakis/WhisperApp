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
from hotkey_manager import HotkeyManager
from window_manager import WindowManager
from command_parser import CommandParser
from application_controller import ApplicationController
from automation_controller import AutomationController
from audio_controller import AudioController
from clipboard_controller import ClipboardController
from file_controller import FileController

# Legacy voice command listener (optional - requires speech_recognition)
try:
    from voice_command_listener import VoiceCommandListener
    LEGACY_VOICE_AVAILABLE = True
except ImportError:
    LEGACY_VOICE_AVAILABLE = False
    print("Note: Legacy voice commands unavailable (speech_recognition not installed)")
    print("JARVIS mode will be used for all voice commands")

# JARVIS AI Components (Python 3.13+ compatible)
from whisper_voice_listener import WhisperVoiceListener
from function_registry import FunctionRegistry
from natural_language_processor import NaturalLanguageProcessor
from text_to_speech import TextToSpeechManager
from conversation_manager import ConversationManager


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

        # Initialize new controllers
        self.app_controller = ApplicationController()
        self.automation_controller = AutomationController()
        self.audio_controller = AudioController()
        self.clipboard_controller = ClipboardController()
        self.file_controller = FileController()

        # Initialize transcription service with API key
        api_key = self.config_manager.get_api_key()
        if not api_key:
            # Try to get from environment variable
            api_key = os.getenv('WHISPER_API_KEY', '')
            if api_key:
                self.config_manager.set_api_key(api_key)

        self.transcription_service = TranscriptionService(api_key)

        # Initialize JARVIS AI components
        self.function_registry = FunctionRegistry(
            self.window_manager,
            self.app_controller,
            self.automation_controller,
            self.audio_controller,
            self.clipboard_controller,
            self.file_controller
        )

        # Get JARVIS settings from config (with defaults)
        jarvis_config = self.config_manager.get('jarvis', {})
        nlu_model = jarvis_config.get('model', 'gpt-4o-mini')  # Production-ready model
        verbosity = jarvis_config.get('response_verbosity', 'balanced')
        tts_voice = jarvis_config.get('voice', 'onyx')  # Deep, authoritative voice perfect for JARVIS
        tts_model = jarvis_config.get('tts_model', 'tts-1-hd')  # High-definition quality
        tts_speed = jarvis_config.get('speaking_speed', 1.0)

        self.nlu_processor = NaturalLanguageProcessor(
            api_key,
            self.function_registry,
            model=nlu_model,
            verbosity=verbosity
        )

        self.tts_manager = TextToSpeechManager(
            api_key,
            voice=tts_voice,
            model=tts_model,
            speed=tts_speed
        )

        self.conversation_manager = ConversationManager(
            self.nlu_processor,
            self.tts_manager
        )

        # JARVIS mode flag (True = JARVIS AI, False = Legacy command mode)
        self.jarvis_mode = jarvis_config.get('enabled', True)  # Default to JARVIS mode
        self.whisper_voice_listener = None

        # State
        self.is_recording = False
        self.transcription_worker = None

        # Setup UI
        self.setup_tray_icon()
        self.setup_hotkeys()

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
        # Check if already running
        if self.jarvis_mode:
            if self.whisper_voice_listener and self.whisper_voice_listener.is_active():
                return
        else:
            if self.voice_listener and self.voice_listener.is_active():
                return

        try:
            # Get settings
            sensitivity = self.config_manager.get_voice_command_setting('sensitivity', 'medium')
            language = self.config_manager.get('language', 'en')

            if self.jarvis_mode:
                # JARVIS Mode: Use WhisperVoiceListener with wake word
                print("Starting JARVIS mode with Whisper voice listener...")

                # Get JARVIS settings
                jarvis_config = self.config_manager.get('jarvis', {})
                wake_word = jarvis_config.get('wake_word', 'jarvis')

                # Create and start Whisper-based listener
                self.whisper_voice_listener = WhisperVoiceListener(
                    self.transcription_service,
                    sensitivity=sensitivity,
                    wake_word=wake_word,
                    language=language if language != 'auto' else None
                )

                # Connect signals
                self.whisper_voice_listener.command_detected.connect(self.on_jarvis_command_detected)
                self.whisper_voice_listener.wake_word_detected.connect(self.on_wake_word_detected)
                self.whisper_voice_listener.error_occurred.connect(self.on_voice_command_error)
                self.whisper_voice_listener.status_changed.connect(self.on_voice_command_status)
                self.whisper_voice_listener.listening_state_changed.connect(self.on_listening_state_changed)

                # Start the listener
                self.whisper_voice_listener.start()

                self.show_notification(
                    "JARVIS Activated",
                    f"Say 'Hey {wake_word.title()}' to activate voice control"
                )

            else:
                # Legacy Mode: Use Google Speech Recognition (if available)
                if not LEGACY_VOICE_AVAILABLE:
                    # Legacy mode not available, force JARVIS mode
                    print("Legacy mode not available, switching to JARVIS mode...")
                    self.jarvis_mode = True
                    self.config_manager.set('jarvis', {'enabled': True})
                    self.start_voice_commands()  # Recursive call will use JARVIS mode
                    return

                print("Starting legacy mode with Google Speech Recognition...")

                # Map language code to speech recognition format
                lang_map = {
                    'en': 'en-US',
                    'es': 'es-ES',
                    'fr': 'fr-FR',
                    'de': 'DE-DE',
                    'it': 'it-IT',
                    'pt': 'pt-PT',
                    'ru': 'ru-RU',
                    'ja': 'ja-JP',
                    'ko': 'ko-KR',
                    'zh': 'zh-CN',
                }
                sr_language = lang_map.get(language, 'en-US')

                # Create and start legacy listener
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
        if self.whisper_voice_listener:
            self.whisper_voice_listener.stop_listening()
            self.whisper_voice_listener.wait(2000)
            self.whisper_voice_listener = None

        if self.voice_listener:
            self.voice_listener.stop_listening()
            self.voice_listener.wait(2000)  # Wait up to 2 seconds for thread to finish
            self.voice_listener = None

        # Stop any ongoing TTS
        if self.conversation_manager:
            self.conversation_manager.stop_speaking()

        mode_name = "JARVIS" if self.jarvis_mode else "Voice Commands"
        self.show_notification(
            f"{mode_name} Disabled",
            "Voice navigation is now inactive"
        )

    def on_voice_command_detected(self, text: str):
        """Handle detected voice command (Legacy mode)"""
        print(f"Voice command detected: {text}")

        # Parse the command
        command = self.command_parser.parse(text)

        if not command:
            # Not a valid command
            print(f"Not a recognized command: {text}")
            return

        # Execute command
        success = self.execute_voice_command(command)

        # Show notification if enabled
        if success and self.config_manager.get_voice_command_setting('show_notifications', True):
            action_desc = self._get_command_description(command)
            self.show_notification("Command Executed", action_desc)

    def on_jarvis_command_detected(self, text: str):
        """Handle detected JARVIS command (AI mode)"""
        print(f"JARVIS command detected: {text}")

        try:
            # Process through conversation manager (includes NLU + TTS)
            response = self.conversation_manager.process_voice_command(
                text,
                speak_response=True
            )

            # Optionally show notification (response will be spoken)
            if self.config_manager.get_voice_command_setting('show_notifications', False):
                # Show brief notification with response
                self.show_notification("JARVIS", response[:100])

        except Exception as e:
            print(f"Error processing JARVIS command: {e}")
            self.show_notification("JARVIS Error", str(e))

    def on_wake_word_detected(self):
        """Handle wake word detection"""
        print("Wake word detected - JARVIS is now listening")

        # Optional: Play a beep sound or show indicator
        self.show_notification("JARVIS", "Yes?", duration=1)

    def on_listening_state_changed(self, is_active: bool):
        """Handle listening state changes"""
        if is_active:
            print("JARVIS is actively listening for commands")
            self.status_action.setText("Status: JARVIS Listening")
        else:
            print("JARVIS returned to wake word listening")
            self.status_action.setText("Status: Listening for wake word")

    def _get_command_description(self, command) -> str:
        """Get a human-readable description of the command"""
        category = command.category
        action = command.action

        if category == 'window':
            if action == 'move_window':
                return f"Moved window to monitor {command.monitor}, quadrant {command.quadrant}"
            else:
                return f"Window: {action.replace('_', ' ').title()}"
        elif category == 'application':
            if command.app_name:
                return f"{action.replace('_', ' ').title()}: {command.app_name}"
            elif command.app_url:
                return f"Opened: {command.app_url}"
        elif category == 'audio':
            if command.volume_level is not None:
                return f"Volume set to {command.volume_level}%"
            else:
                return f"Audio: {action.replace('_', ' ').title()}"
        elif category in ['keyboard', 'mouse']:
            return f"{category.title()}: {action.replace('_', ' ').title()}"
        elif category == 'file':
            if command.folder_name:
                return f"{action.replace('_', ' ').title()}: {command.folder_name}"
            return f"File: {action.replace('_', ' ').title()}"
        elif category == 'clipboard':
            return f"Clipboard: {action.replace('_', ' ').title()}"

        return "Command executed successfully"

    def execute_voice_command(self, command) -> bool:
        """Execute a parsed voice command"""
        try:
            category = command.category
            action = command.action

            # Window Navigation & Operations
            if category == 'window':
                return self._execute_window_command(command)

            # Application Operations
            elif category == 'application':
                return self._execute_app_command(command)

            # Audio Operations
            elif category == 'audio':
                return self._execute_audio_command(command)

            # Keyboard Operations
            elif category == 'keyboard':
                return self._execute_keyboard_command(command)

            # Mouse Operations
            elif category == 'mouse':
                return self._execute_mouse_command(command)

            # File Operations
            elif category == 'file':
                return self._execute_file_command(command)

            # Clipboard Operations
            elif category == 'clipboard':
                return self._execute_clipboard_command(command)

            else:
                print(f"Unknown command category: {category}")
                return False

        except Exception as e:
            print(f"Error executing command: {e}")
            self.show_notification("Command Error", f"Failed to execute: {e}")
            return False

    def _execute_window_command(self, command) -> bool:
        """Execute window-related commands"""
        action = command.action

        if action == 'move_window':
            return self.window_manager.move_window_to_quadrant(
                command.monitor,
                command.quadrant
            )
        elif action == 'minimize_window':
            return self.window_manager.minimize_window()
        elif action == 'maximize_window':
            return self.window_manager.maximize_window()
        elif action == 'close_window':
            return self.window_manager.close_window()
        elif action == 'restore_window':
            return self.window_manager.restore_window()
        elif action == 'center_window':
            return self.window_manager.center_window()
        elif action == 'snap_window':
            position = command.parameters.get('position', 'left')
            return self.window_manager.snap_window(position=position)
        elif action == 'next_monitor':
            return self.window_manager.move_to_next_monitor()
        elif action == 'always_on_top':
            return self.window_manager.set_window_always_on_top()
        else:
            print(f"Unknown window action: {action}")
            return False

    def _execute_app_command(self, command) -> bool:
        """Execute application-related commands"""
        action = command.action

        if action == 'launch_app':
            return self.app_controller.launch_application(command.app_name)
        elif action == 'open_url':
            return self.app_controller.open_url(command.app_url)
        elif action == 'switch_app':
            return self.app_controller.switch_to_application(command.app_name)
        elif action == 'close_app':
            return self.app_controller.close_application(command.app_name, force=False)
        elif action == 'kill_app':
            return self.app_controller.kill_application(command.app_name)
        else:
            print(f"Unknown app action: {action}")
            return False

    def _execute_audio_command(self, command) -> bool:
        """Execute audio-related commands"""
        action = command.action

        if action == 'set_volume':
            return self.audio_controller.set_master_volume(command.volume_level)
        elif action == 'volume_up':
            return self.audio_controller.volume_up()
        elif action == 'volume_down':
            return self.audio_controller.volume_down()
        elif action == 'mute':
            return self.audio_controller.mute()
        elif action == 'unmute':
            return self.audio_controller.unmute()
        elif action == 'toggle_mute':
            return self.audio_controller.toggle_mute()
        else:
            print(f"Unknown audio action: {action}")
            return False

    def _execute_keyboard_command(self, command) -> bool:
        """Execute keyboard-related commands"""
        action = command.action

        if action == 'type_text':
            return self.automation_controller.type_text(command.text_to_type)
        elif action == 'press_keys':
            return self.automation_controller.press_hotkey(*command.key_combo)
        elif action == 'press_shortcut':
            return self.automation_controller.press_hotkey(*command.key_combo)
        elif action == 'save':
            return self.automation_controller.save()
        elif action == 'copy':
            return self.automation_controller.copy()
        elif action == 'paste':
            return self.automation_controller.paste()
        elif action == 'cut':
            return self.automation_controller.cut()
        elif action == 'undo':
            return self.automation_controller.undo()
        elif action == 'redo':
            return self.automation_controller.redo()
        elif action == 'select_all':
            return self.automation_controller.select_all()
        else:
            print(f"Unknown keyboard action: {action}")
            return False

    def _execute_mouse_command(self, command) -> bool:
        """Execute mouse-related commands"""
        action = command.action

        if action == 'click':
            return self.automation_controller.click_mouse()
        elif action == 'double_click':
            return self.automation_controller.double_click()
        elif action == 'right_click':
            return self.automation_controller.right_click()
        elif action == 'scroll':
            params = command.parameters
            direction = params.get('direction', 'down')
            amount = params.get('amount', 3)
            return self.automation_controller.scroll(amount, direction)
        elif action == 'move_mouse':
            x, y = command.position
            return self.automation_controller.move_mouse(x, y)
        else:
            print(f"Unknown mouse action: {action}")
            return False

    def _execute_file_command(self, command) -> bool:
        """Execute file-related commands"""
        action = command.action

        if action == 'open_folder':
            if command.folder_name:
                return self.file_controller.open_folder(command.folder_name)
            elif command.file_path:
                return self.file_controller.open_folder(command.file_path)
        elif action == 'open_file':
            return self.file_controller.open_file(command.file_path)
        elif action == 'create_folder':
            return self.file_controller.create_folder(command.folder_name)
        elif action == 'delete_folder':
            return self.file_controller.delete_folder(command.folder_name)
        else:
            print(f"Unknown file action: {action}")
            return False

        return False

    def _execute_clipboard_command(self, command) -> bool:
        """Execute clipboard-related commands"""
        action = command.action

        if action == 'paste_from_history':
            return self.clipboard_controller.paste_from_history(command.clipboard_index)
        elif action == 'clear_clipboard':
            return self.clipboard_controller.clear_clipboard()
        else:
            print(f"Unknown clipboard action: {action}")
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
            return

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
            return

        # Insert text or copy to clipboard
        auto_copy = self.config_manager.get('auto_copy', True)

        if auto_copy:
            self.text_inserter.copy_to_clipboard(text)

        # Try to insert text (which also copies to clipboard)
        self.text_inserter.insert_text(text)

        # Show notification
        if self.config_manager.get('show_notifications', True):
            self.show_notification(
                "Transcription Complete",
                f"Transcribed: {text[:50]}..." if len(text) > 50 else f"Transcribed: {text}"
            )

    def on_transcription_error(self, error_msg):
        """Handle transcription error"""
        self.status_action.setText("Status: Ready")
        self.show_notification("Transcription Error", error_msg)

    def show_notification(self, title, message, duration=3):
        """Show system notification"""
        try:
            self.tray_icon.showMessage(title, message, QSystemTrayIcon.Information, duration * 1000)
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

        # Update JARVIS components with new API key and settings
        if self.nlu_processor:
            self.nlu_processor.update_api_key(api_key)

        if self.tts_manager:
            self.tts_manager.update_api_key(api_key)

        # Update JARVIS settings if changed
        jarvis_config = self.config_manager.get('jarvis', {})
        if jarvis_config:
            # Update NLU settings
            if self.conversation_manager:
                self.conversation_manager.update_nlu_settings(
                    model=jarvis_config.get('model'),
                    verbosity=jarvis_config.get('response_verbosity')
                )
                self.conversation_manager.update_tts_settings(
                    voice=jarvis_config.get('voice'),
                    model=jarvis_config.get('tts_model'),
                    speed=jarvis_config.get('speaking_speed')
                )

        # Re-register hotkeys if they changed
        self.hotkey_manager.unregister_all()
        self.setup_hotkeys()

        # Restart voice commands if mode changed
        if self.config_manager.is_voice_commands_enabled():
            self.stop_voice_commands()
            self.start_voice_commands()

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
        self.stop_voice_commands()

        # Cleanup JARVIS components
        if self.tts_manager:
            self.tts_manager.cleanup()

        self.audio_recorder.cleanup()
        self.hotkey_manager.unregister_all()
        self.tray_icon.hide()
        self.quit()


def main():
    """Main entry point"""
    app = WhisperApp(sys.argv)
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
