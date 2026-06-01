import logging
import math
import sys
from pathlib import Path
from tempfile import gettempdir
from typing import Callable

from PyQt5.QtCore import QObject, QRectF, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt5.QtWidgets import (
    QAction,
    QApplication,
    QDialog,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QWidget,
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


class RecordingIndicator(QWidget):
    def __init__(self, volume_provider: Callable[[], float] | None = None) -> None:
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(220, 52)
        self._volume_provider = volume_provider or (lambda: 0.0)
        self._phase = 0.0
        self._display_level = 0.0
        self._noise_floor = 0.022
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)

    def show_indicator(self) -> None:
        self._phase = 0.0
        self._display_level = 0.0
        self._position_center_screen()
        self._timer.start()
        self.show()
        self.raise_()

    def hide_indicator(self) -> None:
        self._timer.stop()
        self.hide()

    def _position_center_screen(self) -> None:
        screen = QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        self.move(
            rect.left() + (rect.width() - self.width()) // 2,
            rect.top() + (rect.height() - self.height()) // 2,
        )

    def _tick(self) -> None:
        raw_level = max(0.0, min(1.0, self._volume_provider()))
        active_level = max(0.0, (raw_level - self._noise_floor) / (1.0 - self._noise_floor))
        active_level = active_level ** 0.42

        smoothing = 0.34 if active_level > self._display_level else 0.09
        self._display_level += (active_level - self._display_level) * smoothing
        if self._display_level < 0.006 and active_level <= 0.0:
            self._display_level = 0.0

        if active_level > 0.0 or self._display_level > 0.0:
            self._phase = (self._phase + 0.024 + self._display_level * 0.16) % (math.pi * 2)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        level = self._display_level
        bg = QRectF(0.5, 0.5, self.width() - 1, self.height() - 1)
        frame = QPainterPath()
        frame.moveTo(bg.left() + 14, bg.top())
        frame.lineTo(bg.right() - 22, bg.top())
        frame.lineTo(bg.right(), bg.top() + 14)
        frame.lineTo(bg.right() - 9, bg.bottom() - 5)
        frame.lineTo(bg.right() - 28, bg.bottom())
        frame.lineTo(bg.left() + 12, bg.bottom())
        frame.lineTo(bg.left(), bg.bottom() - 13)
        frame.lineTo(bg.left() + 8, bg.top() + 8)
        frame.closeSubpath()

        painter.setBrush(QColor(3, 6, 9, 238))
        painter.setPen(Qt.NoPen)
        painter.drawPath(frame)

        edge_alpha = 80 + int(level * 125)
        painter.setPen(QPen(QColor(255, 20, 20, edge_alpha), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(frame)
        painter.setPen(QPen(QColor(255, 70, 45, 215), 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(frame)
        painter.setPen(QPen(QColor(255, 180, 120, 95), 0.7, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(17, 7, self.width() - 32, 7)

        painter.setPen(QPen(QColor(255, 54, 42, 23), 1))
        for y in range(11, self.height() - 8, 8):
            painter.drawLine(17, y, self.width() - 22, y)

        painter.setPen(QPen(QColor(38, 235, 188, 52), 1))
        for x in range(46, self.width() - 22, 22):
            painter.drawLine(x, 13, x + 7, 13)
        painter.setPen(QPen(QColor(82, 155, 255, 38), 1))
        for x in range(58, self.width() - 30, 28):
            painter.drawLine(x, 39, x + 5, 39)

        painter.setPen(Qt.NoPen)
        pulse = 8 + level * 7
        painter.setBrush(QColor(255, 31, 28, 36 + int(level * 90)))
        painter.drawEllipse(QRectF(21 - pulse / 2, 22 - pulse / 2, pulse, pulse))
        painter.setBrush(QColor(255, 64, 48, 150 + int(level * 85)))
        painter.drawEllipse(QRectF(17.5, 21.5, 7, 7))
        painter.setBrush(QColor(255, 205, 145, 145 + int(level * 70)))
        painter.drawEllipse(QRectF(19.7, 23.7, 2.6, 2.6))

        width = 154
        left = 45
        center_y = 27
        amplitude = 0.45 + level * 18.0
        path = QPainterPath()
        for x in range(width + 1):
            taper = math.sin((x / width) * math.pi)
            signal = (
                math.sin((x * 0.14) + self._phase * 1.75)
                + math.sin((x * 0.31) - self._phase * 1.1) * 0.5
                + math.sin((x * 0.055) + self._phase * 0.7) * 0.72
            )
            y = center_y + signal * amplitude * (0.18 + taper * 0.82)
            if x == 0:
                path.moveTo(left + x, y)
            else:
                path.lineTo(left + x, y)

        glow_alpha = 34 + int(level * 80)
        core_alpha = 125 + int(level * 120)
        painter.setPen(QPen(QColor(255, 22, 22, glow_alpha), 12, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(255, 44, 34, 80 + int(level * 90)), 6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(255, 96, 64, core_alpha), 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)
        painter.setPen(QPen(QColor(255, 218, 160, 70 + int(level * 95)), 0.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(path)

        painter.setPen(QPen(QColor(255, 170, 105, 70), 0.7))
        painter.drawLine(left - 3, center_y, left + width + 3, center_y)

        painter.setPen(QPen(QColor(255, 54, 36, 55), 1))
        painter.drawLine(33, 10, 42, self.height() - 9)
        painter.drawLine(self.width() - 23, 9, self.width() - 39, self.height() - 8)


class WhisperTrayApp(QObject):
    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)

        self.config_manager = ConfigManager()
        self.settings = self.config_manager.get_settings()

        self.transcription_service = TranscriptionService()
        self.transcription_service.configure(str(self.settings.get("api_key", "")))

        self.audio_recorder = AudioRecorder(
            audio_device=str(self.settings.get("audio_device", "default")),
        )
        self.text_inserter = TextInserter()

        self._is_recording = False
        self._is_transcribing = False
        self._worker_thread = None
        self.recording_indicator = RecordingIndicator(self.audio_recorder.get_volume_level)

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
            hotkey=str(self.settings.get("hotkey", "ctrl+shift+space")),
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
                    "Try running WhisperApp as Administrator."
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

        outer = QPainterPath()
        outer.moveTo(32, 4)
        outer.lineTo(57, 18)
        outer.lineTo(52, 48)
        outer.lineTo(32, 60)
        outer.lineTo(12, 48)
        outer.lineTo(7, 18)
        outer.closeSubpath()

        inner = QPainterPath()
        inner.moveTo(32, 13)
        inner.lineTo(48, 23)
        inner.lineTo(44, 43)
        inner.lineTo(32, 51)
        inner.lineTo(20, 43)
        inner.lineTo(16, 23)
        inner.closeSubpath()

        painter.setBrush(QColor(2, 5, 8, 245))
        painter.setPen(QPen(QColor(255, 28, 24, 150), 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(outer)
        painter.setPen(QPen(QColor(255, 95, 58, 235), 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(outer)

        painter.setBrush(QColor(12, 16, 20, 210))
        painter.setPen(QPen(QColor(255, 46, 34, 185), 1.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawPath(inner)

        painter.setPen(QPen(QColor(255, 52, 38, 230), 3.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(21, 34, 30, 24)
        painter.drawLine(30, 24, 43, 39)
        painter.setPen(QPen(QColor(255, 218, 150, 180), 1.1, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.drawLine(22, 34, 30, 25)
        painter.drawLine(30, 25, 42, 38)

        painter.setPen(QPen(QColor(38, 235, 188, 105), 1))
        painter.drawLine(21, 20, 31, 20)
        painter.setPen(QPen(QColor(82, 155, 255, 82), 1))
        painter.drawLine(34, 47, 44, 47)
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

        # Reconfigure runtime components with new settings
        self.transcription_service.configure(str(self.settings.get("api_key", "")))
        self.audio_recorder.audio_device = str(self.settings.get("audio_device", "default"))

        # Restart hotkey listener if hotkey changed
        old_hotkey = self.hotkey_listener._hotkey if hasattr(self.hotkey_listener, "_hotkey") else ""
        new_hotkey = str(self.settings.get("hotkey", "ctrl+shift+space"))
        if old_hotkey != new_hotkey.lower().replace(" ", ""):
            try:
                self.hotkey_listener.stop()
            except Exception:
                logging.exception("Failed to stop old hotkey listener")
            self.hotkey_listener = HotkeyListener(
                on_start=lambda: QTimer.singleShot(0, self.on_hotkey_pressed),
                on_stop=lambda: QTimer.singleShot(0, self.on_hotkey_released),
                hotkey=new_hotkey,
            )
            try:
                self.hotkey_listener.start()
            except Exception as exc:
                logging.exception("Failed to restart hotkey listener")
                self.set_status("Ready (Hotkey Error)")
                self.notify("Hotkey Error", str(exc))

        self.notify("Settings Updated", "Your settings have been saved.")

    def on_hotkey_pressed(self) -> None:
        if self._is_recording or self._is_transcribing:
            return

        try:
            self.audio_recorder.start_recording()
            self._is_recording = True
            self.recording_indicator.show_indicator()
            self.set_status("Recording...")
            self.notify(
                "Recording Started",
                "Speak now... Release keys to transcribe",
            )
        except Exception as exc:
            logging.exception("Recording start failed")
            self.recording_indicator.hide_indicator()
            self.set_status("Ready")
            self.notify("Recording Error", str(exc))

    def on_hotkey_released(self) -> None:
        if not self._is_recording:
            return

        self._is_recording = False
        self.recording_indicator.hide_indicator()
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
            self.recording_indicator.hide_indicator()
        except Exception:
            logging.exception("Recording indicator shutdown failed")
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
