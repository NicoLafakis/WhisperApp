import time

import keyboard
import pyperclip


class TextInserter:
    def insert_text(self, text: str, auto_copy: bool) -> bool:
        payload = (text or "").strip()
        if not payload:
            return False

        if auto_copy:
            pyperclip.copy(payload)

        time.sleep(0.1)
        pyperclip.copy(payload)
        keyboard.press_and_release("ctrl+v")
        return True
