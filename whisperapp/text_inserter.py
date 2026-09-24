import time

import keyboard
import pyperclip
import ctypes
import os


class TextInserter:
    @staticmethod
    def foreground_window():
        if os.name != "nt":
            return None
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.GetForegroundWindow.restype = ctypes.c_void_p
        return user32.GetForegroundWindow()

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

    # Virtual Key codes for Ctrl, Shift, Alt, Left-Win, Right-Win
    MODIFIER_VKS = (0x11, 0x10, 0x12, 0x5B, 0x5C)

    @staticmethod
    def _is_key_physically_pressed(vk: int) -> bool:
        if os.name != "nt":
            return False
        try:
            user32 = ctypes.windll.user32
            return bool(user32.GetAsyncKeyState(vk) & 0x8000)
        except Exception:
            return False

    @classmethod
    def _modifiers_held(cls) -> bool:
        if os.name == "nt":
            # On Windows, query the physical hardware key state directly.
            # Python's keyboard.is_pressed() tracks hook state which frequently gets
            # desynchronized/stale, artificially blocking paste operations.
            return any(cls._is_key_physically_pressed(vk) for vk in cls.MODIFIER_VKS)
        return any(keyboard.is_pressed(key) for key in ("ctrl", "shift", "alt", "windows"))

    def insert_text(self, text: str, auto_copy: bool) -> bool:
        payload = (text or "").strip()
        if not payload:
            return False

        self.copy_text(payload)
        time.sleep(0.1)
        # The push-to-talk modifiers may still be held when a quick request finishes.
        # Do not turn Ctrl+V into Ctrl+Shift+V (or another app shortcut).
        deadline = time.monotonic() + 0.75
        while self._modifiers_held():
            if time.monotonic() >= deadline:
                return False
            time.sleep(0.025)
        keyboard.press_and_release("ctrl+v")
        return True

    @staticmethod
    def type_text(text: str) -> bool:
        """Type Unicode directly without disturbing a held push-to-talk chord."""
        payload = text or ""
        if not payload:
            return False

        # keyboard.write() temporarily releases held keys. That would release the
        # push-to-talk shortcut and can stop capture mid-phrase. Sending Unicode
        # packets directly leaves physical modifier state and the clipboard alone.
        if os.name == "nt":
            type_unicode = keyboard._os_keyboard.type_unicode
            for character in payload:
                type_unicode(character)
            return True

        keyboard.write(payload)
        return True
