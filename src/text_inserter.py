"""
Text insertion module for WhisperApp
Handles inserting transcribed text into active field or clipboard
"""
import pyperclip
from pynput.keyboard import Controller, Key
import time


class TextInserter:
    """Handles text insertion into active window or clipboard"""

    def __init__(self):
        self.keyboard = Controller()

    def insert_text(self, text):
        """
        Insert text into the active text field

        Returns:
            True if text was inserted, False if copied to clipboard
        """
        try:
            # Give user time to switch back to target window
            time.sleep(0.1)

            # Try to paste by simulating keyboard input
            # First, copy to clipboard
            pyperclip.copy(text)

            # Then paste using Ctrl+V
            self.keyboard.press(Key.ctrl)
            self.keyboard.press('v')
            self.keyboard.release('v')
            self.keyboard.release(Key.ctrl)

            return True
        except Exception as e:
            print(f"Error inserting text: {e}")
            # Fallback to clipboard only
            return False

    def copy_to_clipboard(self, text):
        """Copy text to clipboard"""
        try:
            pyperclip.copy(text)
            return True
        except Exception as e:
            print(f"Error copying to clipboard: {e}")
            return False

    def get_clipboard_text(self):
        """Get current clipboard text"""
        try:
            return pyperclip.paste()
        except Exception as e:
            print(f"Error getting clipboard text: {e}")
            return ""
