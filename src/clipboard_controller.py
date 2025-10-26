"""
Clipboard Controller for WhisperApp
Enhanced clipboard operations including history
"""
import pyperclip
import win32clipboard
import win32con
from typing import List, Optional
from collections import deque


class ClipboardController:
    """Controls clipboard operations with history"""

    def __init__(self, history_size: int = 20):
        """
        Initialize clipboard controller

        Args:
            history_size: Maximum number of clipboard items to remember
        """
        self.history = deque(maxlen=history_size)
        self.history_size = history_size

    # ============= Basic Clipboard Operations =============

    def copy_text(self, text: str) -> bool:
        """
        Copy text to clipboard

        Args:
            text: Text to copy

        Returns:
            True if successful
        """
        try:
            pyperclip.copy(text)
            self._add_to_history(text)
            print(f"Copied to clipboard: {text[:50]}...")
            return True
        except Exception as e:
            print(f"Error copying to clipboard: {e}")
            return False

    def paste_text(self) -> Optional[str]:
        """
        Get text from clipboard

        Returns:
            Clipboard text or None
        """
        try:
            text = pyperclip.paste()
            return text
        except Exception as e:
            print(f"Error pasting from clipboard: {e}")
            return None

    def clear_clipboard(self) -> bool:
        """
        Clear clipboard

        Returns:
            True if successful
        """
        try:
            pyperclip.copy('')
            print("Cleared clipboard")
            return True
        except Exception as e:
            print(f"Error clearing clipboard: {e}")
            return False

    # ============= Clipboard History =============

    def _add_to_history(self, text: str):
        """Add text to clipboard history"""
        if text and text not in list(self.history):
            self.history.appendleft(text)

    def get_history(self) -> List[str]:
        """
        Get clipboard history

        Returns:
            List of clipboard items (most recent first)
        """
        return list(self.history)

    def get_history_item(self, index: int) -> Optional[str]:
        """
        Get specific item from clipboard history

        Args:
            index: History index (0 = most recent)

        Returns:
            Clipboard text or None
        """
        try:
            if 0 <= index < len(self.history):
                return list(self.history)[index]
            return None
        except Exception as e:
            print(f"Error getting history item {index}: {e}")
            return None

    def paste_from_history(self, index: int) -> bool:
        """
        Copy item from history to clipboard

        Args:
            index: History index (0 = most recent)

        Returns:
            True if successful
        """
        item = self.get_history_item(index)
        if item:
            return self.copy_text(item)
        return False

    def clear_history(self):
        """Clear clipboard history"""
        self.history.clear()
        print("Cleared clipboard history")

    # ============= Advanced Clipboard Operations =============

    def append_to_clipboard(self, text: str, separator: str = '\n') -> bool:
        """
        Append text to current clipboard content

        Args:
            text: Text to append
            separator: Separator between old and new content

        Returns:
            True if successful
        """
        try:
            current = self.paste_text() or ''
            new_content = current + separator + text if current else text
            return self.copy_text(new_content)
        except Exception as e:
            print(f"Error appending to clipboard: {e}")
            return False

    def prepend_to_clipboard(self, text: str, separator: str = '\n') -> bool:
        """
        Prepend text to current clipboard content

        Args:
            text: Text to prepend
            separator: Separator between new and old content

        Returns:
            True if successful
        """
        try:
            current = self.paste_text() or ''
            new_content = text + separator + current if current else text
            return self.copy_text(new_content)
        except Exception as e:
            print(f"Error prepending to clipboard: {e}")
            return False

    def get_clipboard_format(self) -> str:
        """
        Get current clipboard format

        Returns:
            Format description
        """
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_TEXT):
                    return 'text'
                elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    return 'unicode_text'
                elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_BITMAP):
                    return 'image'
                elif win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                    return 'files'
                else:
                    return 'unknown'
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Error getting clipboard format: {e}")
            return 'unknown'

    def has_text(self) -> bool:
        """
        Check if clipboard contains text

        Returns:
            True if clipboard has text
        """
        try:
            format_type = self.get_clipboard_format()
            return format_type in ['text', 'unicode_text']
        except:
            return False

    def get_clipboard_size(self) -> int:
        """
        Get size of clipboard content

        Returns:
            Size in characters (for text) or 0
        """
        try:
            text = self.paste_text()
            return len(text) if text else 0
        except:
            return 0

    # ============= File Operations =============

    def copy_file_path(self, file_path: str) -> bool:
        """
        Copy file path to clipboard

        Args:
            file_path: Path to copy

        Returns:
            True if successful
        """
        return self.copy_text(file_path)

    def get_file_paths(self) -> List[str]:
        """
        Get file paths from clipboard (if CF_HDROP format)

        Returns:
            List of file paths
        """
        try:
            win32clipboard.OpenClipboard()
            try:
                if win32clipboard.IsClipboardFormatAvailable(win32con.CF_HDROP):
                    files = win32clipboard.GetClipboardData(win32con.CF_HDROP)
                    return list(files) if files else []
                return []
            finally:
                win32clipboard.CloseClipboard()
        except Exception as e:
            print(f"Error getting file paths from clipboard: {e}")
            return []

    # ============= Utility Methods =============

    def monitor_clipboard(self, callback, interval: float = 0.5):
        """
        Monitor clipboard for changes (blocking)

        Args:
            callback: Function to call with new clipboard content
            interval: Check interval in seconds
        """
        import time

        last_content = self.paste_text()

        try:
            while True:
                time.sleep(interval)
                current_content = self.paste_text()

                if current_content != last_content:
                    last_content = current_content
                    callback(current_content)

        except KeyboardInterrupt:
            print("Stopped monitoring clipboard")

    def save_clipboard_to_file(self, file_path: str) -> bool:
        """
        Save clipboard content to file

        Args:
            file_path: Path to save to

        Returns:
            True if successful
        """
        try:
            content = self.paste_text()
            if content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"Saved clipboard to {file_path}")
                return True
            return False
        except Exception as e:
            print(f"Error saving clipboard to file: {e}")
            return False

    def load_clipboard_from_file(self, file_path: str) -> bool:
        """
        Load clipboard content from file

        Args:
            file_path: Path to load from

        Returns:
            True if successful
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return self.copy_text(content)
        except Exception as e:
            print(f"Error loading clipboard from file: {e}")
            return False
