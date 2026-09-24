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
    monkeypatch.setattr(module.TextInserter, "_is_key_physically_pressed", lambda vk: True)
    monkeypatch.setattr(module.keyboard, "is_pressed", lambda key: True)
    monkeypatch.setattr(module.keyboard, "press_and_release", paste)
    monkeypatch.setattr(module.time, "monotonic", lambda: next(clock))
    assert not module.TextInserter().insert_text("recoverable dictation", True)
    copy.assert_called_once_with("recoverable dictation")
    paste.assert_not_called()


def test_stale_keyboard_hook_does_not_block_paste_when_physical_keys_released(monkeypatch):
    copy, paste = MagicMock(), MagicMock()
    monkeypatch.setattr(module.pyperclip, "copy", copy)
    monkeypatch.setattr(module.keyboard, "is_pressed", lambda key: True)
    monkeypatch.setattr(module.TextInserter, "_is_key_physically_pressed", lambda vk: False)
    monkeypatch.setattr(module.keyboard, "press_and_release", paste)
    assert module.TextInserter().insert_text("fast dictation", True)
    paste.assert_called_once_with("ctrl+v")


def test_physical_key_state_queries_user32_get_async_key_state(monkeypatch):
    user32 = MagicMock()
    user32.GetAsyncKeyState.return_value = 0x8000
    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(module.ctypes.windll, "user32", user32)
    assert module.TextInserter._is_key_physically_pressed(0x11) is True
    user32.GetAsyncKeyState.return_value = 0
    assert module.TextInserter._is_key_physically_pressed(0x11) is False


def test_live_typing_sends_unicode_without_releasing_held_hotkey(monkeypatch):
    typed = []
    os_keyboard = type("OSKeyboard", (), {"type_unicode": staticmethod(typed.append)})()
    monkeypatch.setattr(module.os, "name", "nt")
    monkeypatch.setattr(module.keyboard, "_os_keyboard", os_keyboard, raising=False)
    assert module.TextInserter.type_text("hello é")
    assert typed == list("hello é")

