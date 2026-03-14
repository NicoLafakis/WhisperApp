from typing import Callable, Optional

import keyboard


class HotkeyListener:
    def __init__(
        self,
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
    ) -> None:
        self.on_start = on_start
        self.on_stop = on_stop
        self._press_hook: Optional[object] = None
        self._release_hook: Optional[object] = None
        self._active = False

    def start(self) -> None:
        self._press_hook = keyboard.on_press_key("space", self._handle_press)
        self._release_hook = keyboard.on_release_key("space", self._handle_release)

    def stop(self) -> None:
        if self._press_hook is not None:
            keyboard.unhook(self._press_hook)
            self._press_hook = None
        if self._release_hook is not None:
            keyboard.unhook(self._release_hook)
            self._release_hook = None

    def _handle_press(self, _event: object) -> None:
        if self._active:
            return
        if keyboard.is_pressed("ctrl") and keyboard.is_pressed("shift"):
            self._active = True
            self.on_start()

    def _handle_release(self, _event: object) -> None:
        if self._active:
            self._active = False
            self.on_stop()
