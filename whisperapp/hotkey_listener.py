import logging
from typing import Callable, Optional

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
        hooks = [self._press_hook, self._release_hook]
        self._press_hook = None
        self._release_hook = None

        clean = True
        for hook in hooks:
            if hook is not None and not self._unhook(hook):
                clean = False

        if not clean:
            self._unhook_everything()

        self._active = False
        logger.info("Hotkey listener stopped")

    def _unhook(self, hook: object) -> bool:
        """Remove one hook, working around the ``keyboard`` library's shared-key entry.

        ``keyboard.hook_key`` files every registration under ``_hooks[key]`` as well as
        under the callback, so a press hook and a release hook on the same key overwrite
        each other there. The remove function deletes ``_hooks[key]`` *before* it drops
        the callback from the listener's key store, so the second unhook raises
        ``KeyError`` on the missing entry and the handler is left live - the leak behind
        the ``KeyError: 'space'`` tracebacks that flooded runtime.log.

        Restoring ``_hooks[key]`` for the hook we are about to remove lets the library's
        own remove function run to completion, which is what actually unregisters the
        handler. Returns True when the hook was removed.
        """
        registry = getattr(keyboard, "_hooks", None)
        if isinstance(registry, dict):
            registry[self._primary_key] = hook

        try:
            keyboard.unhook(hook)
            return True
        except Exception:
            logger.debug(
                "Targeted unhook of %r failed; falling back to unhook_all",
                self._primary_key,
                exc_info=True,
            )
            return False

    @staticmethod
    def _unhook_everything() -> None:
        """Last resort: drop every keyboard hook in the process.

        Safe here because WhisperApp is the only consumer of ``keyboard`` hooks in its
        own process, and leaving an orphaned handler registered is strictly worse.
        """
        try:
            keyboard.unhook_all()
        except Exception:
            logger.debug("keyboard.unhook_all() failed", exc_info=True)

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
