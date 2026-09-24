"""Regression tests for defect D4 - hotkey teardown leaves a handler behind.

See docs/FINDINGS-2026-08-27-no-transcription-output.md.

``HotkeyListener.start`` registers ``on_press_key`` and ``on_release_key`` against the
same primary key. The ``keyboard`` library files both under one shared ``_hooks[key]``
entry, so the first unhook removes that entry and the second raises ``KeyError: 'space'``
- and it raises *before* the line that removes the callback from the listener store.
The current code swallows that KeyError with ``logger.exception``, which both floods the
log with tracebacks and hides the fact that the release handler is still live.

The fake in conftest reproduces that shared-entry behaviour exactly, so these tests
assert on the outcome (nothing left registered) rather than on any particular fix.
"""

from __future__ import annotations

import logging
from types import SimpleNamespace

import pytest

from whisperapp import hotkey_listener
from whisperapp.hotkey_listener import HotkeyListener


@pytest.fixture
def listener() -> HotkeyListener:
    return HotkeyListener(on_start=lambda: None, on_stop=lambda: None, hotkey="ctrl+shift+space")


def test_start_registers_press_and_release_hooks(fake_keyboard, listener):
    listener.start()

    assert [(entry.key, entry.kind) for entry in fake_keyboard.registered] == [
        ("space", "press"),
        ("space", "release"),
    ]


def test_stop_leaves_no_handler_registered(fake_keyboard, listener):
    """Both hooks must actually be gone, not just forgotten by the listener."""
    listener.start()

    listener.stop()

    assert fake_keyboard.registered == []


def test_stop_does_not_raise_when_unhook_fails(raising_keyboard, listener):
    listener.start()

    listener.stop()  # must not propagate KeyError: 'space'


def test_stop_is_idempotent(raising_keyboard, listener):
    listener.start()

    listener.stop()
    listener.stop()

    assert raising_keyboard.registered == []


def test_teardown_does_not_log_errors(raising_keyboard, listener, caplog):
    """A routine teardown must not look like a crash in %TEMP%\\whisperapp\\runtime.log.

    The log was full of these tracebacks during the incident, which is noise the next
    person debugging has to wade through before reaching the real 429.
    """
    caplog.set_level(logging.DEBUG, logger="whisperapp.hotkey_listener")
    listener.start()

    listener.stop()

    errors = [record for record in caplog.records if record.levelno >= logging.ERROR]
    assert errors == [], f"teardown logged {[r.getMessage() for r in errors]}"


def test_restart_after_stop_registers_cleanly(fake_keyboard, listener):
    """Changing the hotkey in Settings stops and restarts the listener."""
    listener.start()
    listener.stop()

    listener.start()

    assert len(fake_keyboard.registered) == 2


def test_stale_library_modifier_state_cannot_start_recording(fake_keyboard, monkeypatch):
    starts = []
    listener = HotkeyListener(on_start=lambda: starts.append(True), on_stop=lambda: None)
    # The hook library can retain a modifier after Windows has seen its key-up.
    # A later ordinary space press must not open the microphone.
    monkeypatch.setattr(hotkey_listener, "_physical_hotkey_is_down", lambda keys: False)
    listener._handle_press(object())
    assert starts == []
    assert not listener._active


def test_physically_held_hotkey_still_starts_and_releases(fake_keyboard, monkeypatch):
    events = []
    listener = HotkeyListener(on_start=lambda: events.append("start"),
                              on_stop=lambda: events.append("stop"))
    monkeypatch.setattr(hotkey_listener, "_physical_hotkey_is_down", lambda keys: True)
    listener._handle_press(object())
    listener._handle_release(object())
    assert events == ["start", "stop"]


def test_windows_modifier_check_uses_current_down_bit(monkeypatch):
    class KeyState:
        def __init__(self):
            self.values = {0x11: 0x8000, 0x10: 0x8000}

        def __call__(self, code):
            return self.values.get(code, 0)

    state = KeyState()
    monkeypatch.setattr(hotkey_listener.ctypes, "WinDLL",
                        lambda *_args, **_kwargs: SimpleNamespace(GetAsyncKeyState=state))
    assert hotkey_listener._physical_hotkey_is_down(["ctrl", "shift"])
    state.values[0x10] = 1  # Recently pressed is not currently held.
    assert not hotkey_listener._physical_hotkey_is_down(["ctrl", "shift"])


def test_custom_hotkey_modifier_is_checked_physically(monkeypatch):
    class KeyState:
        def __init__(self):
            self.value = 0

        def __call__(self, code):
            return self.value if code == 0x14 else 0

    state = KeyState()
    class MapScan:
        def __call__(self, scan, _mode):
            return 0x14 if scan == 58 else 0

    mapper = MapScan()
    monkeypatch.setattr(hotkey_listener.ctypes, "WinDLL",
                        lambda *_args, **_kwargs: SimpleNamespace(GetAsyncKeyState=state,
                                                                  MapVirtualKeyW=mapper))
    monkeypatch.setattr(hotkey_listener.keyboard, "key_to_scan_codes", lambda name: (58,))
    assert not hotkey_listener._physical_hotkey_is_down(["capslock"])
    state.value = 0x8000
    assert hotkey_listener._physical_hotkey_is_down(["capslock"])
