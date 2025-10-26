"""
Automation Controller for WhisperApp
Handles keyboard and mouse automation
"""
import keyboard
import time
from pynput.mouse import Button, Controller as MouseController
from pynput.keyboard import Key, Controller as KeyboardController
from typing import Optional, Tuple
import win32api
import win32con


class AutomationController:
    """Controls keyboard and mouse automation"""

    def __init__(self):
        self.mouse = MouseController()
        self.kb = KeyboardController()

        # Key name mappings for voice commands
        self.key_mappings = {
            'enter': Key.enter,
            'return': Key.enter,
            'space': Key.space,
            'spacebar': Key.space,
            'tab': Key.tab,
            'backspace': Key.backspace,
            'delete': Key.delete,
            'escape': Key.esc,
            'esc': Key.esc,
            'up': Key.up,
            'down': Key.down,
            'left': Key.left,
            'right': Key.right,
            'home': Key.home,
            'end': Key.end,
            'pageup': Key.page_up,
            'pagedown': Key.page_down,
            'page up': Key.page_up,
            'page down': Key.page_down,
            'shift': Key.shift,
            'control': Key.ctrl,
            'ctrl': Key.ctrl,
            'alt': Key.alt,
            'win': Key.cmd,
            'windows': Key.cmd,
            'cmd': Key.cmd,
        }

    # ============= Keyboard Control =============

    def type_text(self, text: str, delay: float = 0.0) -> bool:
        """
        Type text with optional delay between characters

        Args:
            text: Text to type
            delay: Delay between characters in seconds

        Returns:
            True if successful
        """
        try:
            for char in text:
                self.kb.type(char)
                if delay > 0:
                    time.sleep(delay)

            print(f"Typed: {text}")
            return True

        except Exception as e:
            print(f"Error typing text: {e}")
            return False

    def press_key(self, key_name: str) -> bool:
        """
        Press and release a single key

        Args:
            key_name: Name of key to press

        Returns:
            True if successful
        """
        try:
            key = self._parse_key(key_name)
            if key is None:
                print(f"Unknown key: {key_name}")
                return False

            if isinstance(key, Key):
                self.kb.press(key)
                self.kb.release(key)
            else:
                self.kb.press(key)
                self.kb.release(key)

            print(f"Pressed key: {key_name}")
            return True

        except Exception as e:
            print(f"Error pressing key {key_name}: {e}")
            return False

    def press_hotkey(self, *keys) -> bool:
        """
        Press a combination of keys (hotkey)

        Args:
            *keys: Key names to press together

        Returns:
            True if successful
        """
        try:
            parsed_keys = []
            for key_name in keys:
                key = self._parse_key(key_name)
                if key is None:
                    print(f"Unknown key: {key_name}")
                    return False
                parsed_keys.append(key)

            # Press all keys
            for key in parsed_keys:
                self.kb.press(key)

            # Small delay
            time.sleep(0.05)

            # Release in reverse order
            for key in reversed(parsed_keys):
                self.kb.release(key)

            print(f"Pressed hotkey: {' + '.join(keys)}")
            return True

        except Exception as e:
            print(f"Error pressing hotkey: {e}")
            return False

    def send_keyboard_shortcut(self, shortcut: str) -> bool:
        """
        Send a keyboard shortcut (e.g., 'ctrl+s', 'ctrl+shift+t')

        Args:
            shortcut: Shortcut string with keys separated by +

        Returns:
            True if successful
        """
        keys = [k.strip().lower() for k in shortcut.split('+')]
        return self.press_hotkey(*keys)

    def _parse_key(self, key_name: str):
        """
        Parse a key name to pynput Key object or character

        Args:
            key_name: Name of key

        Returns:
            Key object or character, or None if unknown
        """
        key_name_lower = key_name.lower().strip()

        # Check special keys
        if key_name_lower in self.key_mappings:
            return self.key_mappings[key_name_lower]

        # Function keys
        if key_name_lower.startswith('f') and key_name_lower[1:].isdigit():
            fn_num = int(key_name_lower[1:])
            if 1 <= fn_num <= 12:
                return getattr(Key, f'f{fn_num}')

        # Single character
        if len(key_name) == 1:
            return key_name

        return None

    # ============= Mouse Control =============

    def get_mouse_position(self) -> Tuple[int, int]:
        """
        Get current mouse position

        Returns:
            Tuple of (x, y) coordinates
        """
        return self.mouse.position

    def move_mouse(self, x: int, y: int, smooth: bool = False) -> bool:
        """
        Move mouse to absolute position

        Args:
            x: X coordinate
            y: Y coordinate
            smooth: If True, move smoothly

        Returns:
            True if successful
        """
        try:
            if smooth:
                current_x, current_y = self.mouse.position
                steps = 20
                for i in range(steps + 1):
                    t = i / steps
                    new_x = int(current_x + (x - current_x) * t)
                    new_y = int(current_y + (y - current_y) * t)
                    self.mouse.position = (new_x, new_y)
                    time.sleep(0.01)
            else:
                self.mouse.position = (x, y)

            print(f"Moved mouse to ({x}, {y})")
            return True

        except Exception as e:
            print(f"Error moving mouse: {e}")
            return False

    def move_mouse_relative(self, dx: int, dy: int) -> bool:
        """
        Move mouse relative to current position

        Args:
            dx: X offset
            dy: Y offset

        Returns:
            True if successful
        """
        try:
            self.mouse.move(dx, dy)
            print(f"Moved mouse by ({dx}, {dy})")
            return True

        except Exception as e:
            print(f"Error moving mouse: {e}")
            return False

    def click_mouse(self, button: str = 'left', clicks: int = 1, interval: float = 0.1) -> bool:
        """
        Click mouse button

        Args:
            button: 'left', 'right', or 'middle'
            clicks: Number of clicks
            interval: Interval between clicks

        Returns:
            True if successful
        """
        try:
            button_map = {
                'left': Button.left,
                'right': Button.right,
                'middle': Button.middle,
            }

            mouse_button = button_map.get(button.lower(), Button.left)

            for _ in range(clicks):
                self.mouse.click(mouse_button)
                if clicks > 1 and interval > 0:
                    time.sleep(interval)

            print(f"Clicked {button} button {clicks} time(s)")
            return True

        except Exception as e:
            print(f"Error clicking mouse: {e}")
            return False

    def double_click(self) -> bool:
        """Double click left mouse button"""
        return self.click_mouse('left', 2, 0.05)

    def right_click(self) -> bool:
        """Right click mouse"""
        return self.click_mouse('right', 1)

    def click_at(self, x: int, y: int, button: str = 'left') -> bool:
        """
        Move mouse to position and click

        Args:
            x: X coordinate
            y: Y coordinate
            button: Mouse button to click

        Returns:
            True if successful
        """
        if self.move_mouse(x, y):
            time.sleep(0.1)  # Brief delay
            return self.click_mouse(button)
        return False

    def drag_mouse(self, start_x: int, start_y: int, end_x: int, end_y: int,
                   button: str = 'left', duration: float = 0.5) -> bool:
        """
        Drag mouse from start to end position

        Args:
            start_x, start_y: Start coordinates
            end_x, end_y: End coordinates
            button: Mouse button to hold
            duration: Duration of drag in seconds

        Returns:
            True if successful
        """
        try:
            button_map = {
                'left': Button.left,
                'right': Button.right,
                'middle': Button.middle,
            }

            mouse_button = button_map.get(button.lower(), Button.left)

            # Move to start position
            self.move_mouse(start_x, start_y)
            time.sleep(0.1)

            # Press button
            self.mouse.press(mouse_button)

            # Drag to end position smoothly
            steps = int(duration * 50)  # 50 steps per second
            for i in range(steps + 1):
                t = i / steps
                x = int(start_x + (end_x - start_x) * t)
                y = int(start_y + (end_y - start_y) * t)
                self.mouse.position = (x, y)
                time.sleep(duration / steps)

            # Release button
            self.mouse.release(mouse_button)

            print(f"Dragged from ({start_x}, {start_y}) to ({end_x}, {end_y})")
            return True

        except Exception as e:
            print(f"Error dragging mouse: {e}")
            return False

    def scroll(self, amount: int, direction: str = 'down') -> bool:
        """
        Scroll mouse wheel

        Args:
            amount: Amount to scroll
            direction: 'up' or 'down'

        Returns:
            True if successful
        """
        try:
            scroll_amount = -amount if direction.lower() == 'down' else amount
            self.mouse.scroll(0, scroll_amount)

            print(f"Scrolled {direction} by {amount}")
            return True

        except Exception as e:
            print(f"Error scrolling: {e}")
            return False

    # ============= Combined Actions =============

    def select_all(self) -> bool:
        """Select all text (Ctrl+A)"""
        return self.press_hotkey('ctrl', 'a')

    def copy(self) -> bool:
        """Copy (Ctrl+C)"""
        return self.press_hotkey('ctrl', 'c')

    def cut(self) -> bool:
        """Cut (Ctrl+X)"""
        return self.press_hotkey('ctrl', 'x')

    def paste(self) -> bool:
        """Paste (Ctrl+V)"""
        return self.press_hotkey('ctrl', 'v')

    def undo(self) -> bool:
        """Undo (Ctrl+Z)"""
        return self.press_hotkey('ctrl', 'z')

    def redo(self) -> bool:
        """Redo (Ctrl+Y)"""
        return self.press_hotkey('ctrl', 'y')

    def save(self) -> bool:
        """Save (Ctrl+S)"""
        return self.press_hotkey('ctrl', 's')

    def find(self) -> bool:
        """Find (Ctrl+F)"""
        return self.press_hotkey('ctrl', 'f')

    def new_tab(self) -> bool:
        """New tab (Ctrl+T)"""
        return self.press_hotkey('ctrl', 't')

    def close_tab(self) -> bool:
        """Close tab (Ctrl+W)"""
        return self.press_hotkey('ctrl', 'w')

    def refresh(self) -> bool:
        """Refresh (F5 or Ctrl+R)"""
        return self.press_key('f5')

    def alt_tab(self) -> bool:
        """Switch windows (Alt+Tab)"""
        return self.press_hotkey('alt', 'tab')
