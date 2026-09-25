from unittest.mock import MagicMock

from whisperapp import text_inserter as module


def test_temporary_clipboard_contention_retries_before_paste(monkeypatch):
    copy = MagicMock(side_effect=[module.pyperclip.PyperclipException("busy"), None])
    paste = MagicMock()
    monkeypatch.setattr(module.pyperclip, "copy", copy)
    monkeypatch.setattr(module.keyboard, "is_pressed", lambda key: False)
    monkeypatch.setattr(module.keyboard, "press_and_release", paste)
    assert module.TextInserter().insert_text("dictation", True)
    assert copy.call_count == 2
    paste.assert_called_once_with("ctrl+v")


def test_held_shortcut_modifiers_do_not_generate_wrong_paste(monkeypatch):
    copy, paste = MagicMock(), MagicMock()
    clock = iter([0.0, 1.0])
    monkeypatch.setattr(module.pyperclip, "copy", copy)
    monkeypatch.setattr(module.keyboard, "is_pressed", lambda key: True)
    monkeypatch.setattr(module.keyboard, "press_and_release", paste)
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    assert not module.TextInserter().insert_text("recoverable dictation", True)
    copy.assert_called_once_with("recoverable dictation")
    paste.assert_not_called()
