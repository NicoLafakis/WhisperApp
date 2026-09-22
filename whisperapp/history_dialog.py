from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import QTimer, QUrl, Qt, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QDialog, QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QPushButton, QTextEdit, QVBoxLayout

from whisperapp.text_inserter import TextInserter


class HistoryDialog(QDialog):
    retry_requested = pyqtSignal(str)

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.setWindowTitle("WhisperApp — Dictation History")
        self.resize(760, 540)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Your recordings and transcriptions are saved here, including failed attempts."))
        self.entries = QListWidget()
        self.entries.currentItemChanged.connect(self.show_entry)
        layout.addWidget(self.entries)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        layout.addWidget(self.detail, 1)
        buttons = QHBoxLayout()
        self.copy_button = QPushButton("Copy Text")
        self.copy_button.clicked.connect(self.copy_text)
        self.retry_button = QPushButton("Retry Recording")
        self.retry_button.clicked.connect(self.retry)
        folder = QPushButton("Open Saved Files")
        folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(store.directory))))
        for button in (self.copy_button, self.retry_button, folder):
            buttons.addWidget(button)
        layout.addLayout(buttons)
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self._timer.start(2000)
        self.refresh()

    def refresh(self):
        selected = self.entries.currentItem()
        selected_path = selected.data(Qt.UserRole) if selected else None
        jobs = list(reversed(self.store.jobs()))
        signature = [(j["path"], j["state"], j.get("attempts"), j.get("error")) for j in jobs]
        if signature == getattr(self, "_signature", None):
            return
        self._signature = signature
        self.entries.clear()
        labels = {"pending": "Queued", "retry": "Waiting to retry", "transcribing": "Transcribing",
                  "recording": "Recording", "completed": "Text saved", "saved": "Audio saved", "failed": "Needs attention"}
        for job in jobs:
            stamp = datetime.fromtimestamp(job.get("created", 0)).strftime("%b %d, %I:%M:%S %p")
            item = QListWidgetItem(f"{stamp} — {labels.get(job['state'], job['state'])}")
            item.setData(Qt.UserRole, job["path"])
            self.entries.addItem(item)
            if job["path"] == selected_path:
                self.entries.setCurrentItem(item)
        if self.entries.currentItem() is None and self.entries.count():
            self.entries.setCurrentRow(0)

    def show_entry(self, item, previous=None):
        path = Path(item.data(Qt.UserRole)) if item else None
        text = self.store.text(path) if path else ""
        job = self.store.read(path) if path else {}
        self.detail.setPlainText(text or job.get("error") or "Audio saved. Transcription will appear here.")
        self.copy_button.setEnabled(bool(text))
        self.retry_button.setEnabled(bool(path and path.exists() and not text
                                          and job.get("state") not in ("recording", "transcribing")))

    def copy_text(self):
        item = self.entries.currentItem()
        if item:
            text = self.store.text(Path(item.data(Qt.UserRole)))
            if text:
                try:
                    TextInserter.copy_text(text)
                    self.copy_button.setText("Copied")
                except Exception:
                    self.copy_button.setText("Clipboard busy — try again")

    def retry(self):
        item = self.entries.currentItem()
        if item:
            self.retry_requested.emit(item.data(Qt.UserRole))
            self.refresh()
