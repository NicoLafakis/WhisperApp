import ctypes
import logging
import sys
import time
from pathlib import Path
from tempfile import gettempdir
from typing import Callable, Optional

from PyQt5.QtCore import QObject, QPoint, QRectF, QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QCursor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
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
from whisperapp.config_manager import ConfigManager, DEFAULT_TRANSCRIPTION_MODEL
from whisperapp.dictation_store import DictationStore
from whisperapp.history_dialog import HistoryDialog
from whisperapp.hotkey_listener import HotkeyListener
from whisperapp.live_transcription import LiveTranscriptionResult, LiveTranscriptionThread
from whisperapp.settings_dialog import SettingsDialog
from whisperapp.text_inserter import TextInserter
from whisperapp.transcription_service import (
    BILLING_URL,
    ERROR_HEADLINES,
    ERROR_STATUSES,
    TranscriptionErrorKind,
    TranscriptionResult,
    TranscriptionService,
)


LOG_DIR = Path(gettempdir()) / "whisperapp"
LOG_FILE = LOG_DIR / "runtime.log"

# httpx and the OpenAI SDK log every request and retry at INFO. Left on, they drown the
# app's own lines - runtime.log reached 1.4 MB and the real 429 was buried in it.
NOISY_LOGGERS = ("httpx", "httpcore", "openai", "urllib3")


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
    for name in NOISY_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)


def handle_uncaught_exception(exc_type, exc_value, exc_traceback) -> None:
    logging.error(
        "Uncaught exception",
        exc_info=(exc_type, exc_value, exc_traceback),
    )


# Per-session, so each logged-in user still gets their own tray app. The name is fixed
# and unguessable-ish rather than random: a second instance has to find the same one.
SINGLE_INSTANCE_MUTEX_NAME = "Local\\WhisperApp-SingleInstance-0f6b1c94b7d24e0a"
_ERROR_ALREADY_EXISTS = 183


class SingleInstanceGuard:
    """Windows named-mutex guard against a second WhisperApp process.

    Two instances double-register the global push-to-talk hotkey and fight over it,
    which is what happened on 2026-08-27.

    A kernel mutex is the documented way to do this. Its lifetime is owned by the OS:
    "the system closes the handle automatically when the process terminates", so a
    crashed instance releases it exactly like a clean exit and the app can never lock
    itself out with a stale lock file.
    https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-createmutexw
    """

    def __init__(self, name: str = SINGLE_INSTANCE_MUTEX_NAME) -> None:
        self._name = name
        self._handle: Optional[int] = None

    def acquire(self) -> bool:
        """True if this process may run; False if another instance already holds it.

        Fails open: if the guard itself cannot be set up, the app still starts.
        """
        if not sys.platform.startswith("win"):
            return True

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateMutexW.argtypes = (
                ctypes.c_void_p,
                ctypes.c_bool,
                ctypes.c_wchar_p,
            )
            kernel32.CreateMutexW.restype = ctypes.c_void_p
            # bInitialOwner=False, per the docs: with several processes racing to create
            # the same named mutex, ownership would otherwise be ambiguous.
            handle = kernel32.CreateMutexW(None, False, self._name)
            last_error = ctypes.get_last_error()
        except Exception:
            logging.warning("Single-instance guard unavailable", exc_info=True)
            return True

        if not handle:
            logging.warning("CreateMutexW failed (error %d); starting anyway", last_error)
            return True

        if last_error == _ERROR_ALREADY_EXISTS:
            self._close(handle)
            return False

        self._handle = handle
        return True

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle:
            self._close(handle)

    @staticmethod
    def _close(handle: int) -> None:
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
            kernel32.CloseHandle.restype = ctypes.c_bool
            kernel32.CloseHandle(handle)
        except Exception:
            # The OS reclaims the handle at process exit regardless.
            logging.debug("CloseHandle on the instance mutex failed", exc_info=True)


class TranscriptionThread(QThread):
    completed = pyqtSignal(object)  # TranscriptionResult
    partial_text = pyqtSignal(str)

    def __init__(self, service: TranscriptionService, wav_path: Path, model: str, language: str, store=None):
        super().__init__()
        self._service = service
        self._wav_path = wav_path
        self._model = model
        self._language = language
        self._store = store

    def run(self) -> None:
        try:
            result = self._service.transcribe(
                wav_path=self._wav_path,
                model=self._model,
                language=self._language,
                on_partial=self.partial_text.emit,
            )
        except Exception as exc:
            logging.exception("Transcription worker crashed")
            result = TranscriptionResult(
                error_kind=TranscriptionErrorKind.UNKNOWN,
                message=str(exc),
            )
        # Save text before handing it to the UI. A quit/crash between the API result
        # and queued Qt callback must not discard a completed transcription.
        if result.ok and result.text.strip() and self._store is not None:
            try:
                self._store.complete(self._wav_path, result.text.strip())
            except Exception:
                logging.exception("Could not persist transcription; retaining result for UI recovery")
        self.completed.emit(result)


class AudioOperationThread(QThread):
    """Run potentially slow PortAudio open/close and WAV finalization off the UI."""

    def __init__(self, operation: str, recorder: AudioRecorder) -> None:
        super().__init__()
        self.operation = operation
        self.recorder = recorder
        self.result = None
        self.error: Optional[Exception] = None

    def run(self) -> None:
        try:
            if self.operation == "start":
                self.recorder.start_recording()
            else:
                self.result = self.recorder.stop_recording()
        except Exception as exc:
            self.error = exc


class RecordingIndicator(QWidget):
    def __init__(
        self,
        volume_provider: Callable[[], float] | None = None,
        position: Optional[tuple[int, int]] = None,
        on_position_changed: Optional[Callable[[int, int], None]] = None,
    ) -> None:
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(260, 60)
        self._volume_provider = volume_provider or (lambda: 0.0)
        self._saved_position = position
        self._on_position_changed = on_position_changed
        self._drag_offset = None
        self._display_level = 0.0
        self._peak_level = 0.008
        self._state = "STARTING"
        self._state_started = time.monotonic()
        self._partial_text = ""
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._tick)
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_indicator)

    def show_indicator(self) -> None:
        self._hide_timer.stop()
        if not self.isVisible():
            self._display_level = 0.0
            self._peak_level = 0.008
            self._state_started = time.monotonic()
            self._position_overlay()
        self._timer.start()
        self.show()
        self.raise_()

    def set_state(self, state: str) -> None:
        self._hide_timer.stop()
        if state != self._state:
            self._state_started = time.monotonic()
            if state != "RECORDING":
                self._display_level = 0.0
        self._state = state
        self.update()

    def set_partial_text(self, text: str) -> None:
        self._partial_text = text
        self.update()

    def hide_indicator(self) -> None:
        self._hide_timer.stop()
        self._timer.stop()
        self.hide()

    def finish(self, state: str, message: str, visible_ms: int) -> None:
        self.show_indicator()
        self.set_state(state)
        self.set_partial_text(message)
        self._hide_timer.start(visible_ms)

    def _position_overlay(self) -> None:
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        if screen is None:
            return
        rect = screen.availableGeometry()
        if self._saved_position is None:
            x, y = rect.right() - self.width() - 18, rect.top() + 18
        else:
            x, y = self._saved_position
        self.move(self._clamp_position(x, y, rect))

    def _clamp_position(self, x: int, y: int, rect) -> QPoint:
        return QPoint(
            max(rect.left(), min(x, rect.right() - self.width() + 1)),
            max(rect.top(), min(y, rect.bottom() - self.height() + 1)),
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            screen = QApplication.screenAt(event.globalPos()) or QApplication.primaryScreen()
            if screen is not None:
                target = event.globalPos() - self._drag_offset
                self.move(self._clamp_position(target.x(), target.y(), screen.availableGeometry()))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton and self._drag_offset is not None:
            self._drag_offset = None
            self._saved_position = (self.x(), self.y())
            if self._on_position_changed is not None:
                self._on_position_changed(*self._saved_position)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def _tick(self) -> None:
        if self._state == "RECORDING":
            raw_level = max(0.0, min(1.0, self._volume_provider()))
            self._peak_level = max(raw_level, self._peak_level * 0.99, 0.008)
            active_level = min(1.0, max(0.0, raw_level - 0.0002) / self._peak_level * 1.3) ** 0.65
            smoothing = 0.42 if active_level > self._display_level else 0.17
            self._display_level += (active_level - self._display_level) * smoothing
            if self._display_level < 0.006 and active_level == 0.0:
                self._display_level = 0.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(QColor(130, 24, 25, 225), 1))
        painter.setBrush(QColor(10, 13, 17, 246))
        painter.drawRoundedRect(QRectF(1, 1, self.width() - 2, self.height() - 2), 12, 12)

        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.setPen(QColor(255, 95, 75))
        label = {
            "STARTING": "OPENING MIC", "RECORDING": "RECORDING", "SAVING": "SAVING",
            "TRANSCRIBING": "PROCESSING", "QUEUED": "QUEUED", "RETRYING": "RETRYING",
            "DONE": "DONE", "FAILED": "FAILED", "TEXT READY": "TEXT READY",
        }.get(self._state, self._state)
        painter.drawText(QRectF(12, 7, 160, 18), Qt.AlignLeft | Qt.AlignVCenter, label)
        if self._state not in ("DONE", "FAILED", "TEXT READY"):
            elapsed = int(time.monotonic() - self._state_started)
            painter.setPen(QColor(150, 160, 170))
            painter.drawText(QRectF(184, 7, 62, 18), Qt.AlignRight | Qt.AlignVCenter,
                             f"{elapsed // 60:02d}:{elapsed % 60:02d}")
        message = self._partial_text or {
            "STARTING": "Opening microphone…",
            "RECORDING": "Listening · phrases type live",
            "SAVING": "Saving recording…",
            "TRANSCRIBING": "Finishing dictation…",
            "QUEUED": "Saved; waiting for earlier dictation…",
            "RETRYING": "Connection interrupted; retrying…",
        }.get(self._state, "")
        painter.setFont(QFont("Segoe UI", 8))
        painter.setPen(QColor(218, 224, 230))
        painter.drawText(QRectF(12, 28, 158, 20), Qt.AlignLeft | Qt.AlignVCenter,
                         painter.fontMetrics().elidedText(message, Qt.ElideRight, 158))

        # KITT's voice module is a compact bank of red LED columns. During capture
        # the lit segments follow the microphone level; after release they pulse
        # separately to show that the saved audio is still being processed.
        painter.setPen(QPen(QColor(83, 28, 31), 1))
        painter.setBrush(QColor(20, 10, 13))
        painter.drawRoundedRect(QRectF(178, 28, 70, 24), 4, 4)
        for column in range(5):
            if self._state == "RECORDING":
                height = max(1, round(self._display_level * (0.72, 0.88, 1.0, 0.88, 0.72)[column] * 3))
            elif self._state in ("DONE", "TEXT READY"):
                height = 3
            elif self._state == "FAILED":
                height = 1
            else:
                height = 2
            for segment in range(3):
                rect = QRectF(184 + column * 12, 48 - segment * 6, 6, 4)
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor(64, 15, 20) if segment >= height else QColor(235, 24, 28))
                painter.drawRoundedRect(rect, 1.2, 1.2)
                if segment < height:
                    painter.setBrush(QColor(255, 103, 75, 115))
                    painter.drawRoundedRect(QRectF(rect.left() + 1, rect.top(), 4, 1.6), 0.7, 0.7)


class WhisperTrayApp(QObject):
    # Emitted from the recorder's capture thread; Qt queues it onto the UI thread.
    max_duration_reached = pyqtSignal(object)  # Optional[Path]
    hotkey_pressed = pyqtSignal()
    hotkey_released = pyqtSignal()
    capture_failed = pyqtSignal(object, str)

    def __init__(self, app: QApplication):
        super().__init__()
        self.app = app
        self.app.setQuitOnLastWindowClosed(False)

        self.config_manager = ConfigManager()
        self.settings = self.config_manager.get_settings()

        self.transcription_service = TranscriptionService()
        self.transcription_service.configure(str(self.settings.get("api_key", "")))

        self._live_worker: Optional[LiveTranscriptionThread] = None
        self._live_result: Optional[LiveTranscriptionResult] = None
        self._live_pending_path: Optional[Path] = None
        self._live_inserted = False
        self._live_typed_phrases: list[str] = []
        self._live_partial_paths: set[str] = set()
        self._live_focus_lost = False
        self._live_error_message = ""
        self.audio_recorder = AudioRecorder(
            audio_device=str(self.settings.get("audio_device", "default")),
            on_max_duration_reached=self.max_duration_reached.emit,
            on_capture_error=lambda message: self.capture_failed.emit(self.audio_recorder.output_path, message),
            on_audio_chunk=self._queue_live_audio,
        )
        self.max_duration_reached.connect(self._on_max_duration_reached)
        self.capture_failed.connect(self._on_capture_error)
        self.hotkey_pressed.connect(self.on_hotkey_pressed, Qt.QueuedConnection)
        self.hotkey_released.connect(self.on_hotkey_released, Qt.QueuedConnection)
        self.text_inserter = TextInserter()

        self._is_recording = False
        self._is_starting = False
        self._is_stopping = False
        self._stop_after_start = False
        self._audio_thread = None
        self._is_transcribing = False
        self._worker_thread = None
        self._retry_thread = None
        self._retry_job_path: Optional[Path] = None
        self._last_recording: Optional[Path] = None
        self._indicator_job_path: Optional[Path] = None
        self._last_text = ""
        self._active_job_path = None
        self._paste_targets = {}
        self._capture_target = None
        self._history_dialog = None
        self._closing = False
        self.store = DictationStore(self.audio_recorder.recordings_dir)
        self.store.recover()
        saved = self.store.jobs()
        if saved:
            self._last_recording = Path(saved[-1]["path"])
            completed = [job for job in saved if job["state"] == "completed"]
            if completed:
                self._last_text = self.store.text(Path(completed[-1]["path"]))
        # The kind of the failure currently on screen, so a run of identical failures
        # does not stack up a modal dialog per attempt.
        self._last_failure_kind: Optional[TranscriptionErrorKind] = None
        saved_position = self.settings.get("meter_position")
        if (isinstance(saved_position, (tuple, list)) and len(saved_position) == 2
                and all(isinstance(value, int) for value in saved_position)):
            saved_position = tuple(saved_position)
        else:
            saved_position = None
        self.recording_indicator = RecordingIndicator(
            self.audio_recorder.get_volume_level,
            position=saved_position,
            on_position_changed=self._save_meter_position,
        )

        self.tray = QSystemTrayIcon(self._create_icon(), self.app)
        self.menu = QMenu()

        self.status_action = QAction("Status: Ready", self.menu)
        self.status_action.setEnabled(False)

        self.settings_action = QAction("Settings", self.menu)
        self.settings_action.triggered.connect(self.open_settings)

        self.retry_action = QAction("Retry Last Recording", self.menu)
        self.retry_action.setEnabled(self._last_recording is not None)
        self.retry_action.triggered.connect(self.retry_last_recording)
        self.copy_action = QAction("Copy Last Transcription", self.menu)
        self.copy_action.setEnabled(bool(self._last_text))
        self.copy_action.triggered.connect(self.copy_last_transcription)
        self.history_action = QAction("Dictation History", self.menu)
        self.history_action.triggered.connect(self.show_history)

        self.about_action = QAction("About", self.menu)
        self.about_action.triggered.connect(self.show_about)

        self.quit_action = QAction("Quit", self.menu)
        self.quit_action.triggered.connect(self.app.quit)

        self.menu.addAction(self.status_action)
        self.menu.addAction(self.retry_action)
        self.menu.addAction(self.copy_action)
        self.menu.addAction(self.history_action)
        self.menu.addSeparator()
        self.menu.addAction(self.settings_action)
        self.menu.addAction(self.about_action)
        self.menu.addSeparator()
        self.menu.addAction(self.quit_action)

        self.tray.setContextMenu(self.menu)
        self.tray.show()
        self.set_status("Ready")

        self.hotkey_listener = HotkeyListener(
            on_start=self.hotkey_pressed.emit,
            on_stop=self.hotkey_released.emit,
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
        self._queue_timer = QTimer(self)
        self._queue_timer.timeout.connect(self._process_queue)
        self._queue_timer.start(1000)

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
        self.tray.setToolTip(f"WhisperApp - {text}")

    def _save_meter_position(self, x: int, y: int) -> None:
        try:
            self.config_manager.save_settings({"meter_position": [x, y]})
            self.settings["meter_position"] = [x, y]
        except Exception:
            logging.warning("Could not save meter position", exc_info=True)

    def _queue_live_audio(self, chunk: bytes) -> None:
        worker = self._live_worker
        if worker is not None and worker.isRunning():
            worker.enqueue_audio(chunk)

    def _on_live_ready(self) -> None:
        if self._is_recording and not self._closing:
            self.recording_indicator.set_partial_text("Live typing ready")
            self.set_status("Recording · live typing")

    def _on_live_failed(self, message: str) -> None:
        self._live_error_message = message
        if not self._is_recording or self._closing:
            return
        self.recording_indicator.set_partial_text("Connection lost; will use saved audio")
        self.set_status("Recording · saved audio fallback")
        logging.warning("Live dictation unavailable: %s", message)

    def _on_live_phrase(self, phrase: str) -> None:
        if self._closing or (not self._is_recording and self._live_pending_path is None) or not phrase:
            return
        if (self._capture_target is None
                or self.text_inserter.foreground_window() != self._capture_target):
            self._live_focus_lost = True
            self.recording_indicator.set_partial_text("Focus changed; text saved in History")
            return
        try:
            if self.text_inserter.type_text(phrase + " "):
                self._live_inserted = True
                self._live_typed_phrases.append(phrase)
        except Exception:
            self._live_focus_lost = True
            logging.warning("Could not type a finalized live phrase", exc_info=True)
            self.recording_indicator.set_partial_text("Typing stopped; audio is saved")

    def _on_live_completed(self, result: LiveTranscriptionResult) -> None:
        self._live_result = result
        if result.error:
            self._on_live_failed(result.error)

    def _on_live_thread_finished(self) -> None:
        path = self._live_pending_path
        if path is not None:
            self._complete_live_capture(path)

    def _finish_live_capture(self, wav_path: Path) -> None:
        self._live_pending_path = wav_path
        worker = self._live_worker
        if worker is None:
            self._start_transcription(wav_path)
            self._live_pending_path = None
            return
        worker.finish_recording()
        self.recording_indicator.set_state("TRANSCRIBING")
        self.recording_indicator.set_partial_text("Finishing live transcript…")
        self.set_status("Finishing live transcript...")
        if not worker.isRunning():
            self._complete_live_capture(wav_path)

    def _complete_live_capture(self, wav_path: Path) -> None:
        if self._live_pending_path != wav_path:
            return
        self._live_pending_path = None
        worker = self._live_worker
        result = self._live_result or getattr(worker, "result", None)
        self._live_worker = None
        if result is None and worker is not None and worker.isRunning():
            # The QThread finished callback can be queued just after isRunning flips.
            self._live_worker = worker
            self._live_pending_path = wav_path
            return

        transcript = result.text.strip() if result is not None else ""
        if result is None or result.error or not transcript:
            if self._live_inserted:
                self._live_partial_paths.add(str(wav_path))
            self._start_transcription(wav_path)
            return

        self._last_recording = wav_path
        self._last_text = transcript
        self.copy_action.setEnabled(True)
        self.retry_action.setEnabled(False)
        try:
            self.store.complete(wav_path, transcript)
        except Exception:
            logging.exception("Could not save live transcript; retaining audio for recovery")
            self.recording_indicator.finish("TEXT READY", "Audio saved; open Dictation History.", 7000)
            self.set_status("Audio saved — transcript could not be saved")
            return

        typed_transcript = " ".join(self._live_typed_phrases).strip()
        fully_typed = typed_transcript == transcript
        if self._live_inserted:
            if bool(self.settings.get("auto_copy", True)):
                try:
                    self.text_inserter.copy_text(transcript)
                except Exception:
                    logging.warning("Could not copy completed live transcript", exc_info=True)
            if fully_typed:
                self.recording_indicator.finish("DONE", "Typed live · saved in History", 2500)
                self.set_status("Dictation complete · typed live")
            else:
                self.recording_indicator.finish("TEXT READY", "Full text saved in History", 6000)
                self.set_status("Full transcript saved; live text may be partial")
        elif (not self._live_focus_lost
              and self.text_inserter.foreground_window() == self._capture_target):
            try:
                self.text_inserter.type_text(transcript)
                if bool(self.settings.get("auto_copy", True)):
                    self.text_inserter.copy_text(transcript)
                self.recording_indicator.finish("DONE", "Text inserted", 2200)
                self.set_status("Dictation complete")
            except Exception:
                logging.exception("Could not insert completed live transcript")
                self.recording_indicator.finish("TEXT READY", "Text saved in Dictation History.", 7000)
                self.set_status("Text saved — open Dictation History")
        else:
            if bool(self.settings.get("auto_copy", True)):
                try:
                    self.text_inserter.copy_text(transcript)
                except Exception:
                    logging.warning("Could not copy transcript after focus changed", exc_info=True)
            self.recording_indicator.finish("TEXT READY", "Text saved in Dictation History.", 7000)
            self.set_status("Text saved — open Dictation History")
        self._live_inserted = False
        self._live_typed_phrases = []
        self._live_focus_lost = False
        self.notify("Dictation Complete", "Your transcription is saved in Dictation History.")

    def notify(
        self,
        title: str,
        text: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.Information,
    ) -> None:
        self.tray.showMessage(title, text, icon, 5000)

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
        # New settings start a new failure episode: let the next failure speak up again.
        self._last_failure_kind = None
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
                on_start=self.hotkey_pressed.emit,
                on_stop=self.hotkey_released.emit,
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
        if self._is_recording or self._closing:
            return

        try:
            self._capture_target = self.text_inserter.foreground_window()
            self._live_result = None
            self._live_pending_path = None
            self._live_inserted = False
            self._live_typed_phrases = []
            self._live_focus_lost = False
            self._live_error_message = ""
            # A new dictation supersedes the paste destination of older queued
            # work; that text remains in history instead of arriving out of order.
            self._paste_targets.clear()
            self._indicator_job_path = None
            self._is_recording = True
            self._is_starting = True
            self._stop_after_start = False
            self.retry_action.setEnabled(False)
            self.recording_indicator.show_indicator()
            self.recording_indicator.set_state("STARTING")
            self.recording_indicator.set_partial_text("")
            self.set_status("Opening microphone...")
            live_worker = LiveTranscriptionThread(
                api_key=str(self.settings.get("api_key", "")),
                language=str(self.settings.get("language", "")),
            )
            live_worker.ready.connect(self._on_live_ready, Qt.QueuedConnection)
            live_worker.phrase_completed.connect(self._on_live_phrase, Qt.QueuedConnection)
            live_worker.failed.connect(self._on_live_failed, Qt.QueuedConnection)
            live_worker.completed.connect(self._on_live_completed, Qt.QueuedConnection)
            live_worker.finished.connect(self._on_live_thread_finished, Qt.QueuedConnection)
            self._live_worker = live_worker
            live_worker.start()
            self._start_audio_operation("start")
        except Exception as exc:
            self._on_audio_start_failed(exc)

    def _start_audio_operation(self, operation: str) -> None:
        worker = AudioOperationThread(operation, self.audio_recorder)
        self._audio_thread = worker
        worker.finished.connect(lambda current=worker: self._on_audio_operation_finished(current))
        worker.start()

    def _on_audio_operation_finished(self, worker: AudioOperationThread) -> None:
        if worker.error is not None:
            if worker.operation == "start":
                if self._live_worker is not None:
                    self._live_worker.finish_recording()
                self._on_audio_start_failed(worker.error)
            else:
                self._is_recording = False
                self._is_stopping = False
                self.recording_indicator.finish("FAILED", "Audio could not be saved. Check Dictation History.", 7000)
                logging.error(
                    "Recording stop failed",
                    exc_info=(type(worker.error), worker.error, worker.error.__traceback__),
                )
                self.retry_action.setEnabled(self._last_recording is not None)
                self.set_status("Failed: recording could not be saved")
                self.notify("Recording Error", str(worker.error), QSystemTrayIcon.Critical)
                if self._live_worker is not None:
                    self._live_worker.finish_recording()
            return

        if worker.operation == "start":
            self._is_starting = False
            if self._closing:
                return
            if self._stop_after_start:
                self._stop_after_start = False
                self.on_hotkey_released()
                return
            self.recording_indicator.set_state("RECORDING")
            self.set_status("Recording...")
            try:
                if self.audio_recorder.output_path is not None:
                    self.store.update(
                        self.audio_recorder.output_path,
                        model="gpt-live-transcribe",
                        language=str(self.settings.get("language", "")),
                    )
            except Exception:
                logging.warning("Could not annotate live recording journal", exc_info=True)
            if self._live_error_message:
                self._on_live_failed(self._live_error_message)
            self.notify("Recording Started", "Speak now... Release keys to transcribe")
            return

        self._is_recording = False
        self._is_stopping = False
        wav_path = worker.result
        if wav_path is None:
            if self._live_worker is not None:
                self._live_worker.finish_recording()
                self._live_worker = None
            self.retry_action.setEnabled(self._last_recording is not None)
            self.set_status("Ready")
            self.notify("No Audio Recorded", "No audio captured for transcription.")
            self.recording_indicator.finish("FAILED", "No audio was captured.", 5000)
            return
        self._finish_live_capture(wav_path)

    def _on_audio_start_failed(self, exc: Exception) -> None:
        self._is_recording = False
        self._is_starting = False
        self._is_stopping = False
        self._stop_after_start = False
        if self._live_worker is not None:
            self._live_worker.finish_recording()
            self._live_worker = None
        logging.error("Recording start failed", exc_info=(type(exc), exc, exc.__traceback__))
        self.retry_action.setEnabled(self._last_recording is not None)
        self.recording_indicator.finish("FAILED", "Microphone could not be opened.", 7000)
        self.set_status("Failed: microphone unavailable")
        self.notify("Recording Error", str(exc))

    def _on_capture_error(self, path, message: str) -> None:
        if not self._is_recording or path != self.audio_recorder.output_path:
            return
        self.on_hotkey_released()
        self.notify("Recording Interrupted", message, QSystemTrayIcon.Warning)

    def on_hotkey_released(self) -> None:
        if not self._is_recording:
            return
        if self._is_starting:
            self._stop_after_start = True
            self.recording_indicator.set_state("SAVING")
            self.set_status("Stopping after microphone opens...")
            return
        if self._is_stopping:
            return

        self._is_stopping = True
        self.recording_indicator.set_state("SAVING")
        self.set_status("Saving recording...")
        self._start_audio_operation("stop")

    def _on_max_duration_reached(self, wav_path) -> None:
        """The recorder cut a runaway take short. Say why, then transcribe what we got."""
        if not self._is_recording:
            return

        self._is_recording = False

        cap = self.audio_recorder.max_duration_seconds
        limit = f"{cap / 60:.0f} minute" if cap >= 90 else f"{cap:g} second"
        logging.warning("Recording stopped at the %s cap", limit)
        self.notify(
            "Recording Stopped",
            f"Recording hit the {limit} limit and stopped on its own. "
            "The hotkey may have been stuck.",
            QSystemTrayIcon.Warning,
        )

        if wav_path is None:
            self.retry_action.setEnabled(self._last_recording is not None)
            self.set_status("Ready")
            self.recording_indicator.finish("FAILED", "No audio was captured.", 5000)
            return

        self._finish_live_capture(wav_path)

    def retry_last_recording(self) -> None:
        if self._is_recording or self._is_transcribing or self._last_recording is None:
            return
        if not self._last_recording.is_file():
            self._last_recording = None
            self.retry_action.setEnabled(False)
            self.notify("Recording Unavailable", "The saved recording no longer exists.")
            return
        self.retry_recording(str(self._last_recording))

    def show_history(self) -> None:
        if self._history_dialog is None:
            self._history_dialog = HistoryDialog(self.store)
            self._history_dialog.retry_requested.connect(self.retry_recording)
        self._history_dialog.refresh()
        self._history_dialog.show()
        self._history_dialog.raise_()
        self._history_dialog.activateWindow()

    def retry_recording(self, path: str) -> None:
        wav_path = Path(path)
        if wav_path in (self._active_job_path, self._retry_job_path) or not wav_path.is_file():
            return
        if self.store.text(wav_path):
            self.show_history()
            return
        self._paste_targets.pop(path, None)
        if not self._enqueue(wav_path):
            return

    def _start_transcription(self, wav_path: Path) -> None:
        self._last_recording = wav_path
        self._indicator_job_path = wav_path
        self._paste_targets[str(wav_path)] = self._capture_target
        if not self._enqueue(wav_path):
            return
        if self._is_transcribing and self._active_job_path != wav_path and not self._is_recording:
            self.recording_indicator.set_state("QUEUED")
            self.recording_indicator.set_partial_text("Saved; waiting for earlier dictation…")
            self.set_status("Recording saved — queued for transcription")

    def _enqueue(self, wav_path: Path) -> bool:
        try:
            self.store.enqueue(wav_path, str(self.settings.get("model", DEFAULT_TRANSCRIPTION_MODEL)),
                               str(self.settings.get("language", "en")))
        except Exception:
            logging.exception("Could not queue saved recording")
            self.notify("Audio Saved", "Could not queue transcription. Your recording is in Dictation History.", QSystemTrayIcon.Critical)
            if not self._is_recording:
                self.recording_indicator.finish("FAILED", "Audio saved; open Dictation History.", 7000)
            return False
        self._process_queue()
        return True

    def _process_queue(self) -> None:
        if self._closing:
            return
        retry_running = self._retry_thread is not None and self._retry_thread.isRunning()
        foreground_running = (self._worker_thread is not None
                              and self._worker_thread is not self._retry_thread
                              and self._worker_thread.isRunning())
        # A fresh take gets its own lane even when an old network retry is busy.
        if foreground_running:
            return
        try:
            job = self.store.next_job(include_retries=not self._is_recording and not retry_running)
            if job is None:
                return
            wav_path = Path(job["path"])
            is_retry = job["state"] == "retry"
            self.store.update(wav_path, state="transcribing", attempts=job.get("attempts", 0) + 1)
        except Exception:
            logging.exception("Could not read or update transcription queue")
            if not self._is_recording:
                self.recording_indicator.finish("FAILED", "Audio saved; queue unavailable.", 7000)
            return
        if is_retry:
            self._retry_job_path = wav_path
            if not retry_running and not foreground_running:
                self._active_job_path = wav_path
        else:
            self._active_job_path = wav_path
        self._is_transcribing = True
        self.retry_action.setEnabled(False)
        if not self._is_recording:
            if self._indicator_job_path is None:
                self._indicator_job_path = wav_path
            if self._indicator_job_path == wav_path:
                self.recording_indicator.show_indicator()
                self.recording_indicator.set_state("TRANSCRIBING")
                self.recording_indicator.set_partial_text("")
                self.set_status("Transcribing saved audio...")
        worker = TranscriptionThread(
            service=self.transcription_service,
            wav_path=wav_path,
            model=str(job.get("model", self.settings.get("model", DEFAULT_TRANSCRIPTION_MODEL))),
            language=str(job.get("language", self.settings.get("language", "en"))),
            store=self.store,
        )
        worker.completed.connect(lambda result, path=wav_path: self._on_transcription_finished(result, path))
        worker.partial_text.connect(lambda text, path=wav_path: self._on_transcription_partial(text, path))
        worker.finished.connect(self._process_queue)
        if is_retry:
            self._retry_thread = worker
        if not is_retry or self._worker_thread is None or not self._worker_thread.isRunning():
            self._worker_thread = worker
        worker.start()

    def _on_transcription_partial(self, text: str, wav_path: Optional[Path] = None) -> None:
        wav_path = wav_path or self._active_job_path
        if (self._is_recording or self._closing or not self._is_transcribing
                or wav_path != self._indicator_job_path):
            return
        self.recording_indicator.set_state("TRANSCRIBING")
        self.recording_indicator.set_partial_text(text)

    def _on_transcription_finished(self, result: TranscriptionResult, wav_path: Optional[Path] = None) -> None:
        if self._closing:
            return
        wav_path = wav_path or self._active_job_path
        display_current = not self._is_recording and wav_path == self._indicator_job_path
        if display_current:
            self._indicator_job_path = None
        if wav_path == self._active_job_path:
            self._active_job_path = None
        if wav_path == self._retry_job_path:
            self._retry_job_path = None
        self._is_transcribing = self._active_job_path is not None or self._retry_job_path is not None
        self.retry_action.setEnabled(not self._is_recording and not self._is_transcribing
                                     and self._last_recording is not None)

        if not result.ok or not result.text.strip():
            self._live_partial_paths.discard(str(wav_path))
            kind = result.error_kind or TranscriptionErrorKind.UNKNOWN
            message = result.message or "OpenAI returned no text."
            message = f"{message} Audio is saved in Dictation History; the clipboard was left unchanged."
            if wav_path is not None:
                try:
                    job = self.store.read(wav_path)
                    transient = kind in (TranscriptionErrorKind.CONNECTION_FAILED, TranscriptionErrorKind.RATE_LIMITED,
                                         TranscriptionErrorKind.SERVICE_UNAVAILABLE)
                    delay = min(60, 2 ** min(job.get("attempts", 1), 6))
                    self.store.update(wav_path, state="retry" if transient else "failed",
                                      next_retry=time.time() + delay, error=message)
                    if transient:
                        if display_current:
                            self.set_status("Audio saved — retrying; clipboard unchanged")
                            self.recording_indicator.set_state("RETRYING")
                            self.recording_indicator.set_partial_text(
                                f"Connection interrupted; retrying in {delay}s…"
                            )
                        if job.get("attempts", 1) == 1:
                            self.notify("Audio Saved", "Connection interrupted. WhisperApp will retry automatically. You can keep dictating.")
                        return
                except Exception:
                    logging.exception("Could not save transcription failure state")
                self._paste_targets.pop(str(wav_path), None)
            if display_current:
                self.recording_indicator.finish("FAILED", "Audio saved; check Dictation History.", 7000)
            self._report_failure(kind, message, show_status=display_current)
            return

        text = result.text.strip()
        self._last_failure_kind = None
        if wav_path == self._last_recording:
            self._last_text = text
            self.copy_action.setEnabled(True)
        if wav_path is not None:
            try:
                self.store.complete(wav_path, text)
            except Exception:
                logging.exception("Failed to save text; exposing it for manual recovery")
                QMessageBox.warning(None, "Text Could Not Be Saved", "Copy this text now:\n\n" + text)
        target = self._paste_targets.pop(str(wav_path), None)
        if str(wav_path) in self._live_partial_paths:
            self._live_partial_paths.discard(str(wav_path))
            if bool(self.settings.get("auto_copy", True)):
                try:
                    self.text_inserter.copy_text(text)
                except Exception:
                    logging.warning("Could not copy fallback transcript", exc_info=True)
            if display_current:
                self.recording_indicator.finish("DONE", "Saved in History · live text kept", 5000)
                self.set_status("Saved in History · live text already typed")
            self.notify(
                "Dictation Saved",
                "The saved recording was transcribed for History. Existing live text was left in place.",
            )
            return
        if wav_path != self._last_recording and target is None:
            # A background recovery must not replace the clipboard or last-text
            # action after a newer take has already completed.
            self.notify("Earlier Dictation Saved", "An older transcription is ready in Dictation History.")
            return
        # Recovered/backlogged text must not be pasted into an unrelated window.
        if self._is_recording or target is None or target != self.text_inserter.foreground_window():
            if bool(self.settings.get("auto_copy", True)):
                try:
                    self.text_inserter.copy_text(text)
                    if display_current:
                        self.set_status("Text saved and copied — open Dictation History")
                        self.recording_indicator.finish("DONE", "Text copied. Paste with Ctrl+V.", 3500)
                except Exception:
                    logging.exception("Clipboard copy failed for completed transcription")
                    if display_current:
                        self.set_status("Text saved — open Dictation History")
                        self.recording_indicator.finish("TEXT READY", "Text saved; copy from Dictation History.", 7000)
            elif display_current:
                self.set_status("Text saved — open Dictation History")
                self.recording_indicator.finish("TEXT READY", "Text saved in Dictation History.", 7000)
            self.notify("Dictation Saved", "Your text is ready in Dictation History and Copy Last Transcription.")
            return
        try:
            inserted = self.text_inserter.insert_text(
                text=text,
                auto_copy=bool(self.settings.get("auto_copy", True)),
            )
        except Exception:
            logging.exception("Text insertion failed; transcription retained")
            inserted = False
        if not inserted:
            if display_current:
                self.set_status("Transcribed: use Copy Last Transcription")
            self.notify("Text Ready", "Automatic paste failed. Use Copy Last Transcription in the tray menu.")
            if display_current:
                self.recording_indicator.finish("TEXT READY", "Paste failed; copy from tray menu.", 7000)
            return
        if display_current:
            self.set_status("Ready")
            self.recording_indicator.finish("DONE", "Text inserted.", 1800)

        if bool(self.settings.get("show_notifications", True)):
            self.notify("Transcription Complete", text)

    def copy_last_transcription(self) -> None:
        if not self._last_text:
            return
        try:
            self.text_inserter.copy_text(self._last_text)
        except Exception:
            logging.exception("Clipboard copy failed")
            self.notify("Clipboard Busy", "Could not copy text. Try Copy Last Transcription again.")
            return
        self.notify("Text Copied", "Paste your transcription with Ctrl+V.")

    def _report_failure(self, kind: TranscriptionErrorKind, message: str, *, show_status: bool = True) -> None:
        """Surface a failure so it cannot be mistaken for success.

        The tray status used to be reset to "Ready" before notifying, which made a total
        failure look identical to a clean run once the balloon faded. The status now
        holds the failure until the next recording starts, and it says which failure.
        """
        headline = ERROR_HEADLINES.get(kind, "Transcription Failed")
        detail = (message or "").strip() or "The API returned no detail. See the log."
        logging.error("Transcription failed (%s): %s", kind.name, detail)

        if show_status and not self._is_recording:
            self.set_status(ERROR_STATUSES.get(kind, "Failed"))
        self.notify(headline, detail, QSystemTrayIcon.Critical)

        is_new_episode = kind is not self._last_failure_kind
        self._last_failure_kind = kind

        # A balloon is easy to miss and Focus Assist can swallow it outright. Quota
        # exhaustion is the one failure the user can only fix off-app, so it gets a
        # modal naming the billing page - once per episode, not once per attempt.
        if kind is TranscriptionErrorKind.QUOTA_EXHAUSTED and is_new_episode and not self._is_recording:
            QMessageBox.critical(
                None,
                headline,
                (
                    f"{detail}\n\n"
                    f"Add credits at:\n{BILLING_URL}\n\n"
                    "WhisperApp cannot transcribe until the account has credit."
                ),
            )
        elif kind is TranscriptionErrorKind.NOT_CONFIGURED and is_new_episode and not self._is_recording:
            QMessageBox.warning(
                None,
                headline,
                f"{detail}\n\nOpen Settings from the tray icon to add your OpenAI API key.",
            )

    def cleanup(self) -> None:
        self._closing = True
        self._queue_timer.stop()
        try:
            self.recording_indicator.hide_indicator()
        except Exception:
            logging.exception("Recording indicator shutdown failed")
        try:
            self.hotkey_listener.stop()
        except Exception:
            logging.exception("Hotkey listener shutdown failed")
        if self._audio_thread is not None:
            self._audio_thread.wait()
        try:
            self.audio_recorder.terminate()
        except Exception:
            logging.exception("Audio recorder shutdown failed")
        if self._live_worker is not None:
            self._live_worker.finish_recording()
            self._live_worker.wait(5000)
        # The worker saves its result before exiting. Do not destroy QThread while
        # it is running; queued jobs remain on disk if the process is terminated.
        if self._worker_thread is not None:
            self._worker_thread.wait()
        if self._retry_thread is not None and self._retry_thread is not self._worker_thread:
            self._retry_thread.wait()
        for worker in {self._worker_thread, self._retry_thread} - {None}:
            for signal in (worker.completed, worker.partial_text, worker.finished):
                try:
                    signal.disconnect()
                except (TypeError, RuntimeError):
                    pass


def main() -> int:
    configure_logging()
    sys.excepthook = handle_uncaught_exception

    app = QApplication(sys.argv)
    app.setApplicationName("WhisperApp")
    app.setQuitOnLastWindowClosed(False)

    guard = SingleInstanceGuard()
    if not guard.acquire():
        logging.warning("Another WhisperApp instance is already running; exiting")
        QMessageBox.information(
            None,
            "WhisperApp Already Running",
            (
                "WhisperApp is already running.\n\n"
                "Look for its icon in the system tray, next to the clock - you may need "
                "to click the arrow to show hidden icons."
            ),
        )
        return 0

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
    try:
        return app.exec_()
    finally:
        # Hold the mutex until cleanup (including the current worker) has finished.
        guard.release()


if __name__ == "__main__":
    raise SystemExit(main())
