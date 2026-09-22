import time

import keyboard
import pyperclip


class TextInserter:
    @staticmethod
    def copy_text(text: str) -> None:
        for attempt in range(3):
            try:
                pyperclip.copy(text)
                return
            except pyperclip.PyperclipException:
                if attempt == 2:
                    raise
                time.sleep(0.05)

    def insert_text(self, text: str, auto_copy: bool) -> bool:
        payload = (text or "").strip()
        if not payload:
            return False

        self.copy_text(payload)
        time.sleep(0.1)
        # The push-to-talk modifiers may still be held when a quick request finishes.
        # Do not turn Ctrl+V into Ctrl+Shift+V (or another app shortcut).
        deadline = time.monotonic() + 0.75
        while any(keyboard.is_pressed(key) for key in ("ctrl", "shift", "alt", "windows")):
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.025)
        keyboard.press_and_release("ctrl+v")
        return True
