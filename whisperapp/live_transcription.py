"""Realtime microphone transcription, independent of the durable WAV writer."""

from __future__ import annotations

import asyncio
import base64
import logging
import math
import queue
import threading
from array import array
from dataclasses import dataclass
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal


logger = logging.getLogger(__name__)

INPUT_RATE = 16000
REALTIME_RATE = 24000
SILENCE_SECONDS = 0.55
VOICE_RMS_THRESHOLD = 150
MAX_PHRASE_SECONDS = 12.0
QUEUE_CHUNKS = 250


@dataclass(frozen=True)
class LiveTranscriptionResult:
    text: str = ""
    error: str = ""


class _LinearResampler:
    """Small stateful PCM16 resampler for the fixed 16 kHz -> 24 kHz path."""

    def __init__(self) -> None:
        self._samples = array("h")
        self._position = 0.0

    def convert(self, pcm: bytes) -> bytes:
        incoming = array("h")
        incoming.frombytes(pcm)
        if not incoming:
            return b""
        self._samples.extend(incoming)
        output = array("h")
        step = INPUT_RATE / REALTIME_RATE
        while self._position + 1 < len(self._samples):
            left = int(self._position)
            fraction = self._position - left
            sample = self._samples[left] + (self._samples[left + 1] - self._samples[left]) * fraction
            output.append(max(-32768, min(32767, round(sample))))
            self._position += step
        consumed = min(int(self._position), max(0, len(self._samples) - 1))
        if consumed:
            del self._samples[:consumed]
            self._position -= consumed
        return output.tobytes()


def _rms(pcm: bytes) -> float:
    samples = array("h")
    samples.frombytes(pcm)
    if not samples:
        return 0.0
    return math.sqrt(sum(sample * sample for sample in samples) / len(samples))


class LiveTranscriptionThread(QThread):
    """Stream microphone chunks, commit short phrases, and return final text."""

    phrase_completed = pyqtSignal(str)
    ready = pyqtSignal()
    failed = pyqtSignal(str)
    completed = pyqtSignal(object)  # LiveTranscriptionResult

    def __init__(self, api_key: str, language: str = "") -> None:
        super().__init__()
        self._api_key = api_key
        self._language = language
        self._audio: queue.Queue[bytes] = queue.Queue(maxsize=QUEUE_CHUNKS)
        self._capture_done = threading.Event()
        self._overflowed = threading.Event()
        self._failure_sent = False
        self.result: Optional[LiveTranscriptionResult] = None

    def enqueue_audio(self, chunk: bytes) -> bool:
        if self._capture_done.is_set() or self._overflowed.is_set():
            return False
        try:
            self._audio.put_nowait(chunk)
            return True
        except queue.Full:
            self._overflowed.set()
            return False

    def finish_recording(self) -> None:
        self._capture_done.set()

    def run(self) -> None:
        try:
            result = asyncio.run(self._transcribe())
        except Exception as exc:
            logger.warning("Realtime transcription failed; saved WAV will be used", exc_info=True)
            self._notify_failure(str(exc))
            result = LiveTranscriptionResult(error=str(exc))
        self.result = result
        self.completed.emit(result)

    def _notify_failure(self, message: str) -> None:
        if not self._failure_sent:
            self._failure_sent = True
            self.failed.emit(message)

    async def _transcribe(self) -> LiveTranscriptionResult:
        if not self._api_key.strip():
            raise RuntimeError("Add an OpenAI API key to use live typing.")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self._api_key)
        whole_text: list[str] = []
        item_sequences: dict[str, int] = {}
        pending_results: dict[int, str] = {}
        next_sequence = 0
        next_to_emit = 0
        completed_count = 0
        sent_commits = 0
        completed_event = asyncio.Event()

        language_options = {"languages": [self._language]} if self._language else {}
        session_audio = {
            "format": {"type": "audio/pcm", "rate": REALTIME_RATE},
            "transcription": {
                "model": "gpt-live-transcribe",
                "delay": "low",
                **language_options,
            },
            "turn_detection": None,
        }

        try:
            async with client.realtime.connect(model="gpt-realtime") as connection:
                await connection.session.update(
                    session={
                        "type": "realtime",
                        "audio": {"input": session_audio},
                    }
                )
                self.ready.emit()

                async def receive_events() -> None:
                    nonlocal next_sequence, next_to_emit, completed_count
                    async for event in connection:
                        if event.type == "input_audio_buffer.committed":
                            item_sequences[event.item_id] = next_sequence
                            next_sequence += 1
                        elif event.type == "conversation.item.input_audio_transcription.completed":
                            sequence = item_sequences.get(event.item_id)
                            if sequence is None:
                                continue
                            pending_results[sequence] = event.transcript.strip()
                            completed_count += 1
                            while next_to_emit in pending_results:
                                phrase = pending_results.pop(next_to_emit)
                                next_to_emit += 1
                                if phrase:
                                    whole_text.append(phrase)
                                    self.phrase_completed.emit(phrase)
                            completed_event.set()
                        elif event.type == "error":
                            error = getattr(getattr(event, "error", None), "message", "Realtime transcription error")
                            raise RuntimeError(error)

                receiver = asyncio.create_task(receive_events())
                try:
                    sent_commits = await self._send_audio(connection, receiver)
                    # The service sends a final event after each committed phrase.
                    # Wait briefly for those final events before closing the session.
                    deadline = asyncio.get_running_loop().time() + 4.0
                    while completed_count < sent_commits and asyncio.get_running_loop().time() < deadline:
                        completed_event.clear()
                        try:
                            await asyncio.wait_for(completed_event.wait(), timeout=0.2)
                        except asyncio.TimeoutError:
                            if receiver.done():
                                receiver.result()
                                break
                    if completed_count < sent_commits:
                        raise TimeoutError("Live transcript did not finish before the session closed.")
                finally:
                    receiver.cancel()
                    await asyncio.gather(receiver, return_exceptions=True)
        finally:
            await client.close()

        return LiveTranscriptionResult(text=" ".join(whole_text))

    async def _send_audio(self, connection, receiver: asyncio.Task) -> int:
        resampler = _LinearResampler()
        preroll: list[bytes] = []
        phrase_active = False
        silence_samples = 0
        phrase_samples = 0
        chunks_per_second = max(1, round(16000 / 1024))
        silence_limit = round(SILENCE_SECONDS * chunks_per_second)
        max_phrase_chunks = round(MAX_PHRASE_SECONDS * chunks_per_second)
        commits = 0

        async def append_chunk(chunk: bytes) -> None:
            converted = resampler.convert(chunk)
            if converted:
                await connection.input_audio_buffer.append(
                    audio=base64.b64encode(converted).decode("ascii")
                )

        while True:
            if self._overflowed.is_set():
                raise RuntimeError("The live connection fell behind the microphone; using the saved recording instead.")
            try:
                chunk = await asyncio.to_thread(self._audio.get, True, 0.1)
            except queue.Empty:
                if self._capture_done.is_set():
                    break
                if receiver.done():
                    receiver.result()
                    raise RuntimeError("Realtime connection closed during recording.")
                continue

            loud = _rms(chunk) >= VOICE_RMS_THRESHOLD
            if not phrase_active:
                preroll.append(chunk)
                preroll = preroll[-3:]
                if loud:
                    phrase_active = True
                    silence_samples = 0
                    phrase_samples = 0
                    for buffered in preroll:
                        await append_chunk(buffered)
                        phrase_samples += 1
                    preroll.clear()
                continue

            await append_chunk(chunk)
            phrase_samples += 1
            silence_samples = 0 if loud else silence_samples + 1
            if silence_samples >= silence_limit or phrase_samples >= max_phrase_chunks:
                await connection.input_audio_buffer.commit()
                commits += 1
                phrase_active = False
                silence_samples = 0
                phrase_samples = 0

        if phrase_active:
            await connection.input_audio_buffer.commit()
            commits += 1

        # Publish the number of committed phrases for the receiver drain loop.
        return commits
