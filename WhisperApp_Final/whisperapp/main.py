import logging
import sys
from pathlib import Path
from tempfile import gettempdir

from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
)

from whisperapp.audio_recorder import AudioRecorder
from whisperapp.config_manager import ConfigManager
from whisperapp.hotkey_listener import HotkeyListener
from whisperapp.settings_dialog import SettingsDialog
from whisperapp.text_inserter import TextInserter
from whisperapp.transcription_service import TranscriptionService


LOG_DIR = Path(gettempdir()) / "whisperapp"
LOG_FILE = LOG_DIR / "runtime.log"


def configure_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    logging.error(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


class TranscriptionThread(QThread):
    finished_text = pyqtSignal(str)

    def __init__(self, service: TranscriptionService, wav_path: Path, model: str, language: str):
        super().__init__()
        self._service = service
        self._wav_path = wav_path
        self._model = model
        self._language = language

    def run(self) -> None:
        text = self._service.transcribe(
            wav_path=self._wav_path,
            model=self._model,
            language=self._language,
        )
        self.finished_text.emit(text)


class WhisperTrayApp(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)

        self.config_manager = ConfigManager()
        self.settings = self.config_manager.get_settings()

        self.transcription_service = TranscriptionService()
        self.transcription_service.configure(str(self.settings.get("api_key", "")))

        self.audio_recorder = AudioRecorder()
        self.text_inserter = TextInserter()

        self._is_recording = False
        self._is_transcribing = False
        self._worker_thread = None

        self.tray = QSystemTrayIcon(self._create_icon(), self.app)
        self.menu = QMenu()

        self.status_action = QAction("Status: Ready", self.menu)
        self.status_action.setEnabled(False)

        self.settings_action = QAction("Settings", self.menu)
        self.settings_action.triggered.connect(self.open_settings)

        self.about_action = QAction("About", self.menu)
        self.about_action.triggered.connect(self.show_about)

        self.quit_action = QAction("Quit", self.menu)
        self.quit_action.triggered.connect(self.app.quit)

        self.menu.addAction(self.status_action)
        self.menu.addSeparator()
        self.menu.addAction(self.settings_action)
        self.menu.addAction(self.about_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.show()

        self.hotkey_listener = HotkeyListener(
            on_start=lambda: QTimer.singleShot(0, self.on_hotkey_pressed),
            on_stop=lambda: QTimer.singleShot(0, self.on_hotkey_released),
        )

        try:
            self.hotkey_listener.start()
        except Exception as exc:
            logging.exception("Failed to initialize global hotkey listener")
            self.set_status("Ready (Hotkey Error)")
            self.notify(
                "Hotkey Error",
                "Global hotkey failed. Try running the launcher as Administrator.",
            )
            QMessageBox.warning(
                None,
                "WhisperApp Hotkey Error",
                (
                    "Global hotkey could not be initialized.\n\n"
                    f"{exc}\n\n"
                    "Try running Start-WhisperApp.bat as Administrator."
                ),
            )

        self.app.aboutToQuit.connect(self.cleanup)

        self.notify(
            "WhisperApp Started",
            "Press Ctrl+Shift+Space to start transcription",
        )

        if not self.settings.get("api_key", ""):
            self.notify(
                "API Key Required",
                "Open Settings from the tray icon to configure your OpenAI API key.",
            )
            QTimer.singleShot(800, self.show_welcome)

    def _create_icon(self) -> QIcon:
        pixmap = QPixmap(64, 64)
        pixmap.fill(QColor(0, 0, 0, 0))
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor(28, 89, 170))
        painter.setPen(QColor(20, 65, 120))
        painter.drawEllipse(4, 4, 56, 56)
        painter.setPen(QColor(255, 255, 255))
        painter.drawText(pixmap.rect(), Qt.AlignCenter, "W")
        painter.end()
        return QIcon(pixmap)

    def set_status(self, text: str) -> None:
        self.status_action.setText(f"Status: {text}")

    def notify(self, title: str, text: str) -> None:
        self.tray.showMessage(title, text, QSystemTrayIcon.Information, 5000)

    def show_welcome(self) -> None:
        QMessageBox.information(
            None,
            "Welcome to WhisperApp",
            "Open Settings from the tray icon and add your OpenAI API key.",
        )

    def show_about(self) -> None:
        QMessageBox.information(
            None,
            "About WhisperApp",
            "WhisperApp\n\nPush-to-talk transcription from the system tray.",
        )

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.settings, self.transcription_service)
        if dialog.exec_() != QDialog.Accepted:
            return

        new_settings = dialog.get_settings()
        self.config_manager.save_settings(new_settings)
        self.settings = self.config_manager.get_settings()
        self.transcription_service.configure(str(self.settings.get("api_key", "")))
        self.notify("Settings Updated", "Your settings have been saved.")

    def on_hotkey_pressed(self) -> None:
        if self._is_recording or self._is_transcribing:
            return

        try:
            self.audio_recorder.start_recording()
            self._is_recording = True
            self.set_status("Recording...")
            self.notify(
                "Recording Started",
                "Speak now... Release keys to transcribe",
            )
        except Exception as exc:
            logging.exception("Recording start failed")
            self.set_status("Ready")
            self.notify("Recording Error", str(exc))

    def on_hotkey_released(self) -> None:
        if not self._is_recording:
            return

        self._is_recording = False
        self.set_status("Transcribing...")
        self._is_transcribing = True

        wav_path = self.audio_recorder.stop_recording()
        if wav_path is None:
            self._is_transcribing = False
            self.set_status("Ready")
            self.notify("No Audio Recorded", "No audio captured for transcription.")
            return

        self._worker_thread = TranscriptionThread(
            service=self.transcription_service,
            wav_path=wav_path,
            model=str(self.settings.get("model", "whisper-1")),
            language=str(self.settings.get("language", "en")),
        )
        self._worker_thread.finished_text.connect(self._on_transcription_finished)
        self._worker_thread.start()

    def _on_transcription_finished(self, result_text: str) -> None:
        self._is_transcribing = False
        self.set_status("Ready")

        text = (result_text or "").strip()
        if not text:
            self.notify("Transcription Error", "Error: Empty transcription response")
            return

        if text.startswith("Error:"):
            self.notify("Transcription Error", text)
            return

        self.text_inserter.insert_text(
            text=text,
            auto_copy=bool(self.settings.get("auto_copy", True)),
        )

        if bool(self.settings.get("show_notifications", True)):
            self.notify("Transcription Complete", text)

    def cleanup(self) -> None:
        try:
            self.hotkey_listener.stop()
        except Exception:
            logging.exception("Hotkey listener shutdown failed")
        try:
            self.audio_recorder.terminate()
        except Exception:
            logging.exception("Audio recorder shutdown failed")


def main() -> int:
    configure_logging()
    sys.excepthook = handle_uncaught_exception

    app = QApplication(sys.argv)
    app.setApplicationName("WhisperApp")
    app.setQuitOnLastWindowClosed(False)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        logging.error("System tray is not available")
        QMessageBox.critical(None, "WhisperApp", "System tray is not available.")
        return 1

    try:
        _tray_app = WhisperTrayApp(app)
    except Exception:
        logging.exception("Fatal startup error")
        QMessageBox.critical(
            None,
            "WhisperApp",
            f"Startup failed.\nSee log: {LOG_FILE}",
        )
        return 1

    logging.info("WhisperApp started")
    return app.exec_()


if __name__ == "__main__":
    raise SystemExit(main())
