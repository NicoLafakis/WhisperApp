import asyncio
from array import array
from types import SimpleNamespace

import openai

from whisperapp.live_transcription import LiveTranscriptionThread, _LinearResampler, _rms


def pcm(value: int, count: int = 1024) -> bytes:
    return array("h", [value] * count).tobytes()


def test_linear_resampler_converts_capture_chunks_to_24khz_pcm():
    converter = _LinearResampler()
    first = converter.convert(pcm(1200))
    second = converter.convert(pcm(1200))
    assert len(first) > 0
    assert len(first + second) == 6142
    assert _rms(first + second) == 1200


def test_live_audio_queue_is_bounded_and_stops_accepting_after_capture():
    worker = LiveTranscriptionThread("test-key")
    for _ in range(worker._audio.maxsize):
        assert worker.enqueue_audio(b"chunk")
    assert not worker.enqueue_audio(b"overflow")
    worker.finish_recording()
    assert not worker.enqueue_audio(b"late")


def test_live_session_commits_a_phrase_and_returns_its_final_text(monkeypatch):
    class FakeConnection:
        def __init__(self):
            self.events = asyncio.Queue()
            self.appended = []
            self.commits = 0
            self.session = SimpleNamespace(update=self.update)
            self.input_audio_buffer = SimpleNamespace(append=self.append, commit=self.commit)

        async def update(self, *, session):
            assert session["type"] == "transcription"
            assert session["audio"]["input"]["format"]["rate"] == 24000
            assert session["audio"]["input"]["transcription"]["languages"] == ["en"]

        async def append(self, *, audio):
            self.appended.append(audio)

        async def commit(self):
            self.commits += 1
            item_id = f"item-{self.commits}"
            await self.events.put(SimpleNamespace(type="input_audio_buffer.committed", item_id=item_id))
            await self.events.put(SimpleNamespace(
                type="conversation.item.input_audio_transcription.completed",
                item_id=item_id,
                transcript=f"phrase {self.commits}",
            ))

        def __aiter__(self):
            return self

        async def __anext__(self):
            return await self.events.get()

    connection = FakeConnection()

    class FakeConnectionContext:
        async def __aenter__(self):
            return connection

        async def __aexit__(self, *_args):
            return False

    closed = []

    async def close_client():
        closed.append(True)

    client = SimpleNamespace(
        realtime=SimpleNamespace(connect=lambda **_kwargs: FakeConnectionContext()),
        close=close_client,
    )
    monkeypatch.setattr(openai, "AsyncOpenAI", lambda **_kwargs: client)
    worker = LiveTranscriptionThread("test-key", "en")
    worker.enqueue_audio(pcm(1500))
    for _ in range(10):
        worker.enqueue_audio(pcm(0))
    worker.finish_recording()

    result = asyncio.run(worker._transcribe())

    assert result.text == "phrase 1"
    assert connection.commits == 1
    assert connection.appended
    assert closed == [True]
