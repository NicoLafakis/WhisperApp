"""Durable per-recording journal. Never prune unfinished dictations or their text."""

import json
import os
import threading
import time
import uuid
import struct
import math
import logging
from pathlib import Path

from whisperapp.config_manager import DEFAULT_TRANSCRIPTION_MODEL


def atomic_text(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class DictationStore:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def read(self, wav_path: Path) -> dict:
        with self._lock:
            source = wav_path if wav_path.exists() else wav_path.with_suffix(".txt")
            fallback_created = source.stat().st_mtime
            try:
                data = json.loads(wav_path.with_suffix(".json").read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("Invalid dictation journal")
            except (OSError, ValueError):
                data = {}
            states = {"saved", "recording", "pending", "retry", "transcribing", "completed", "failed"}
            if not isinstance(data.get("state"), str) or data["state"] not in states:
                data["state"] = "saved"
            for field, fallback in (("created", fallback_created), ("next_retry", 0)):
                value = data.get(field)
                if type(value) not in (int, float) or value < 0 or value > 253402300799 or not math.isfinite(value):
                    data[field] = fallback
            if type(data.get("attempts")) is not int or data["attempts"] < 0:
                data["attempts"] = 0
            for field in ("model", "language", "error"):
                if field in data and not isinstance(data[field], str):
                    del data[field]
            if data.get("model") == "gpt-live-transcribe":
                data["model"] = DEFAULT_TRANSCRIPTION_MODEL
            data["path"] = str(wav_path)
            # Text is committed first, so interrupted metadata writes cannot hide it.
            if wav_path.with_suffix(".txt").exists():
                data["state"] = "completed"
            return data

    def update(self, wav_path: Path, **changes) -> dict:
        with self._lock:
            data = self.read(wav_path)
            data.update(changes)
            atomic_text(wav_path.with_suffix(".json"), json.dumps(data, ensure_ascii=False, indent=2))
            return data

    def enqueue(self, wav_path: Path, model: str, language: str) -> None:
        self.update(wav_path, state="pending", model=model, language=language,
                    attempts=0, next_retry=0, error="")

    def complete(self, wav_path: Path, text: str) -> None:
        with self._lock:
            atomic_text(wav_path.with_suffix(".txt"), text)
            self.update(wav_path, state="completed", error="", next_retry=0)

    def text(self, wav_path: Path) -> str:
        try:
            return wav_path.with_suffix(".txt").read_text(encoding="utf-8")
        except OSError:
            return ""

    def jobs(self) -> list:
        jobs = []
        paths = {p.with_suffix(".wav") for pattern in ("recording_*.wav", "recording_*.txt")
                 for p in self.directory.glob(pattern)}
        for path in paths:
            try:
                jobs.append(self.read(path))
            except OSError:
                continue
        return sorted(jobs, key=lambda job: job.get("created", 0))

    def recover(self) -> None:
        for job in self.jobs():
            if job["state"] in ("recording", "transcribing"):
                path = Path(job["path"])
                try:
                    if job["state"] == "recording":
                        self._repair_interrupted_wav(path)
                    changes = {"state": "pending", "next_retry": 0}
                    if job.get("model") == "gpt-live-transcribe":
                        changes["model"] = DEFAULT_TRANSCRIPTION_MODEL
                    self.update(path, **changes)
                except OSError:
                    logging.exception("Could not recover %s; preserving it for manual recovery", path.name)

    @staticmethod
    def _repair_interrupted_wav(path: Path) -> None:
        # Our PCM writer uses a 44-byte header. A kill between appending a chunk
        # and updating its lengths must not make the appended audio inaccessible.
        with path.open("r+b") as handle:
            header = handle.read(44)
            if len(header) != 44 or header[:4] != b"RIFF" or header[36:40] != b"data":
                return
            alignment = struct.unpack_from("<H", header, 32)[0]
            if not alignment:
                return
            size = (path.stat().st_size - 44) // alignment * alignment
            handle.seek(4)
            handle.write(struct.pack("<I", 36 + size))
            handle.seek(40)
            handle.write(struct.pack("<I", size))
            handle.flush()
            os.fsync(handle.fileno())

    def next_job(self, now=None, include_retries=True):
        now = time.time() if now is None else now
        jobs = self.jobs()
        # New dictations should not wait behind older connection-failure retries.
        # Preserve creation order within each class and keep every retry durable.
        for state in (("pending", "retry") if include_retries else ("pending",)):
            due = next((job for job in jobs if job["state"] == state
                        and job.get("next_retry", 0) <= now), None)
            if due is not None:
                return due
        return None
