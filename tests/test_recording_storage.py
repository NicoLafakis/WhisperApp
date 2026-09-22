"""Tests for where recordings live, how many are kept, and the one-time migration.

Recordings used to be written to ``%TEMP%\\whisperapp``, where Windows Disk Cleanup
(and any "free up space" sweep) could delete a take the user had not transcribed yet,
and where nobody would ever think to look for one. They now live under the user's
Documents folder, which on a OneDrive-redirected machine is *not*
``Path.home() / "Documents"`` - hence the known-folder resolution these tests pin.

Nothing here touches the real Documents folder: ``fake_pyaudio`` redirects both the
Documents root and the legacy temp root into ``tmp_path``.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from whisperapp import audio_recorder as ar
from whisperapp.dictation_store import DictationStore


def _touch_wav(path: Path, *, mtime: float) -> Path:
    """Write a placeholder recording with an explicit modification time."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"RIFF....WAVE")
    os.utime(path, (mtime, mtime))
    return path


def _names(directory: Path) -> set:
    return {p.name for p in directory.glob("*.wav")}


# --------------------------------------------------------------------------------------
# Where recordings live
# --------------------------------------------------------------------------------------


def test_recordings_go_under_documents_not_the_temp_dir(fake_pyaudio, tmp_path):
    recorder = ar.AudioRecorder()
    try:
        assert recorder.recordings_dir == tmp_path / "Documents" / "WhisperApp" / "recordings"
        assert recorder.recordings_dir.is_dir()
    finally:
        recorder.terminate()


def test_temp_dir_alias_still_points_at_the_recordings_dir(fake_pyaudio):
    """Kept so older callers and tests that reach for ``temp_dir`` keep working."""
    recorder = ar.AudioRecorder()
    try:
        assert recorder.temp_dir == recorder.recordings_dir
    finally:
        recorder.terminate()


def test_documents_resolution_falls_back_to_the_home_folder(monkeypatch, tmp_path):
    """A machine where neither the known folder nor the registry answers still works."""
    monkeypatch.setattr(ar, "_documents_dir", lambda: None)
    monkeypatch.setattr(ar.Path, "home", staticmethod(lambda: tmp_path))

    assert ar._resolve_recordings_dir() == tmp_path / "Documents" / "WhisperApp" / "recordings"


def test_documents_dir_is_resolvable_on_this_machine():
    """Sanity check on the real resolver - skipped where the concept does not apply."""
    if os.name != "nt":
        pytest.skip("known-folder resolution is Windows-only")

    documents = ar._documents_dir()

    assert documents is not None, "no Documents folder could be resolved"
    assert documents.is_absolute()


# --------------------------------------------------------------------------------------
# Retention
# --------------------------------------------------------------------------------------


def test_retention_default_is_twenty_five():
    assert ar.MAX_RETAINED_RECORDINGS == 25


def test_starting_a_take_prunes_only_completed_audio(fake_pyaudio, tmp_path):
    recorder = ar.AudioRecorder()
    try:
        now = time.time()
        # 30 takes, oldest first: recording_00 is the stalest.
        for index in range(30):
            path = _touch_wav(
                recorder.recordings_dir / f"recording_{index:02d}.wav",
                mtime=now - (30 - index) * 60,
            )
            DictationStore(recorder.recordings_dir).complete(path, f"Finished dictation {index}")

        # The prune runs when a take starts, so the directory is trimmed before the
        # new WAV lands - assert on that moment rather than after the take is written.
        recorder.start_recording()

        survivors = _names(recorder.recordings_dir)
        expected = {f"recording_{index:02d}.wav" for index in range(30 - 25, 30)}
        expected.add(recorder.output_path.name)
        assert survivors == expected, "pruning did not keep completed audio plus the active take"
        assert len(list(recorder.recordings_dir.glob("*.txt"))) == 30

        recorder.stop_recording()
    finally:
        recorder.terminate()


def test_pruning_never_deletes_the_take_being_recorded(fake_pyaudio, monkeypatch):
    """The take being recorded has to survive the prune that runs when it is written,
    even when every other file in the directory is newer than it."""
    monkeypatch.setattr(ar, "MAX_RETAINED_RECORDINGS", 2)

    recorder = ar.AudioRecorder()
    try:
        now = time.time()
        for index in range(5):
            _touch_wav(
                recorder.recordings_dir / f"recording_{index}.wav",
                mtime=now + 3600 + index,  # all *newer* than the take about to be made
            )

        recorder.start_recording()
        in_flight = recorder.output_path
        assert in_flight is not None
        time.sleep(0.05)  # let the capture thread produce at least one chunk

        path = recorder.stop_recording()

        assert path == in_flight
        assert in_flight.exists(), "the take just recorded was pruned away"
    finally:
        recorder.terminate()


def test_retention_preserves_all_unfinished_and_legacy_recordings(fake_pyaudio):
    recorder = ar.AudioRecorder()
    try:
        store = DictationStore(recorder.recordings_dir)
        for index in range(40):
            path = _touch_wav(recorder.recordings_dir / f"recording_pending_{index}.wav", mtime=time.time() - index)
            if index % 2:
                store.update(path, state="retry", next_retry=0)
        recorder._cleanup_old_recordings()
        assert len(_names(recorder.recordings_dir)) == 40
    finally:
        recorder.terminate()


# --------------------------------------------------------------------------------------
# One-time migration out of %TEMP%
# --------------------------------------------------------------------------------------


def test_migration_moves_old_recordings_and_removes_the_old_directory(
    fake_pyaudio, tmp_path
):
    legacy = tmp_path / "whisperapp"
    now = time.time()
    _touch_wav(legacy / "recording_aaa.wav", mtime=now - 500)
    _touch_wav(legacy / "recording_bbb.wav", mtime=now - 400)

    recorder = ar.AudioRecorder()
    try:
        moved = recorder.recordings_dir
        assert _names(moved) == {"recording_aaa.wav", "recording_bbb.wav"}
        assert (moved / "recording_aaa.wav").stat().st_mtime == pytest.approx(
            now - 500, abs=2
        )
        assert not legacy.exists(), "the emptied legacy directory was left behind"
    finally:
        recorder.terminate()


def test_migration_never_overwrites_an_existing_recording(fake_pyaudio, tmp_path):
    legacy = tmp_path / "whisperapp"
    destination = tmp_path / "Documents" / "WhisperApp" / "recordings"
    _touch_wav(legacy / "recording_dup.wav", mtime=time.time() - 100)
    _touch_wav(destination / "recording_dup.wav", mtime=time.time())
    (destination / "recording_dup.wav").write_bytes(b"KEEP ME")

    recorder = ar.AudioRecorder()
    try:
        assert (destination / "recording_dup.wav").read_bytes() == b"KEEP ME"
    finally:
        recorder.terminate()


def test_migration_leaves_non_recording_files_alone(fake_pyaudio, tmp_path):
    """The legacy directory is also the log directory - logs must not be dragged along."""
    legacy = tmp_path / "whisperapp"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "whisperapp.log").write_text("log line\n", encoding="utf-8")

    recorder = ar.AudioRecorder()
    try:
        assert (legacy / "whisperapp.log").exists()
        assert not (recorder.recordings_dir / "whisperapp.log").exists()
    finally:
        recorder.terminate()


def test_migration_preserves_queue_and_transcript_sidecars(fake_pyaudio):
    source = ar._legacy_recordings_dir()
    source.mkdir(parents=True)
    store = DictationStore(source)
    completed = _touch_wav(source / "recording_completed.wav", mtime=time.time())
    store.complete(completed, "Recovered paragraph")
    pending = _touch_wav(source / "recording_pending.wav", mtime=time.time())
    store.enqueue(pending, "gpt-transcribe", "en")
    pruned = _touch_wav(source / "recording_pruned.wav", mtime=time.time())
    store.complete(pruned, "Text without retained audio")
    pruned.unlink()
    recorder = ar.AudioRecorder()
    try:
        migrated = DictationStore(recorder.recordings_dir)
        assert migrated.text(recorder.recordings_dir / completed.name) == "Recovered paragraph"
        assert migrated.text(recorder.recordings_dir / pruned.name) == "Text without retained audio"
        assert migrated.next_job()["path"] == str(recorder.recordings_dir / pending.name)
        assert not source.exists()
    finally:
        recorder.terminate()


def test_migration_collision_keeps_original_audio_and_companions(fake_pyaudio):
    source = ar._legacy_recordings_dir()
    source.mkdir(parents=True)
    destination = ar._prepare_recordings_dir()
    old = _touch_wav(source / "recording_collision.wav", mtime=time.time())
    DictationStore(source).complete(old, "Original text")
    target = _touch_wav(destination / old.name, mtime=time.time())
    DictationStore(destination).complete(target, "Destination text")
    ar._migrate_legacy_recordings(destination)
    assert DictationStore(source).text(old) == "Original text"
    assert DictationStore(destination).text(target) == "Destination text"


def test_a_broken_legacy_directory_does_not_stop_the_app(fake_pyaudio, monkeypatch):
    def explode(*args, **kwargs):
        raise OSError("access denied")

    monkeypatch.setattr(ar.shutil, "move", explode)

    legacy = ar._legacy_recordings_dir()
    _touch_wav(legacy / "recording_zzz.wav", mtime=time.time())

    recorder = ar.AudioRecorder()  # must not raise
    try:
        assert recorder.recordings_dir.is_dir()
    finally:
        recorder.terminate()
