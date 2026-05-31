import logging
from typing import Callable, List, Optional

import keyboard


logger = logging.getLogger(__name__)


class HotkeyListener:
    """Global push-to-talk hotkey listener.

    Supports configurable chord hotkeys (e.g. ``ctrl+shift+space``).
    The listener registers a press hook on the *primary* key and checks
    that all *modifier* keys are held before firing *on_start*.
    Releasing the primary key fires *on_stop*.
    """

    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        hotkey: str = "ctrl+shift+space",
    ) -> None:
        self.on_start = on_start
        self.on_stop = on_stop
        self._hotkey = hotkey.lower().replace(" ", "")
        self._press_hook: Optional[object] = None
        self._release_hook: Optional[object] = None
        self._active = False

        parts = self._hotkey.split("+")
        # The last part is the primary key; everything before it is a modifier.
        self._primary_key = parts[-1]
        self._modifiers = parts[:-1]

    def start(self) -> None:
        try:
            self._press_hook = keyboard.on_press_key(
                self._primary_key, self._handle_press
            )
            self._release_hook = keyboard.on_release_key(
                self._primary_key, self._handle_release
            )
            logger.info("Hotkey listener started for %s", self._hotkey)
        except Exception:
            logger.exception("Failed to start hotkey listener for %s", self._hotkey)
            raise

    def stop(self) -> None:
        if self._press_hook is not None:
            try:
                keyboard.unhook(self._press_hook)
            except Exception:
                logger.exception("Failed to unhook press handler")
            self._press_hook = None
        if self._release_hook is not None:
            try:
                keyboard.unhook(self._release_hook)
            except Exception:
                logger.exception("Failed to unhook release handler")
            self._release_hook = None
        logger.info("Hotkey listener stopped")

    def _modifiers_pressed(self) -> bool:
        for mod in self._modifiers:
            if not keyboard.is_pressed(mod):
                return False
        return True

    def _handle_press(self, _event: object) -> None:
        if self._active:
            return
        if self._modifiers_pressed():
            self._active = True
            self.on_start()

    def _handle_release(self, _event: object) -> None:
        if self._active:
            self._active = False
            self.on_stop()
