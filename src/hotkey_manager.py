"""
Hotkey Manager for WhisperApp
Handles registration and management of global hotkeys
"""
import keyboard
from typing import Callable, Dict, Optional, List


class HotkeyManager:
    """Manages global hotkeys for the application"""

    def __init__(self):
        self.registered_hotkeys: Dict[str, Callable] = {}
        self.active_hooks: Dict[str, List] = {}

    def parse_hotkey(self, hotkey_string: str) -> List[str]:
        """
        Parse hotkey string into list of keys

        Args:
            hotkey_string: Hotkey string like "ctrl+shift+space"

        Returns:
            List of key names
        """
        return [key.strip().lower() for key in hotkey_string.split('+')]

    def validate_hotkey(self, hotkey_string: str) -> tuple[bool, str]:
        """
        Validate hotkey string format

        Args:
            hotkey_string: Hotkey string to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not hotkey_string or not hotkey_string.strip():
            return False, "Hotkey cannot be empty"

        keys = self.parse_hotkey(hotkey_string)

        if len(keys) < 1:
            return False, "Hotkey must contain at least one key"

        # Valid modifier keys
        valid_modifiers = ['ctrl', 'shift', 'alt', 'win', 'cmd']

        # Check for known key names
        for key in keys:
            # Allow alphanumeric, function keys, and special keys
            if not (
                key.isalnum() or
                key.startswith('f') and key[1:].isdigit() or  # Function keys
                key in valid_modifiers or
                key in ['space', 'enter', 'tab', 'esc', 'backspace', 'delete',
                       'up', 'down', 'left', 'right', 'home', 'end', 'pageup', 'pagedown',
                       'insert', 'pause', 'scroll', 'num', 'caps']
            ):
                return False, f"Unknown key: {key}"

        return True, ""

    def register_push_to_talk(self, hotkey_string: str,
                            on_press: Callable,
                            on_release: Callable) -> bool:
        """
        Register a push-to-talk style hotkey

        Args:
            hotkey_string: Hotkey combination (e.g., "ctrl+shift+space")
            on_press: Callback when all keys are pressed
            on_release: Callback when any key is released

        Returns:
            True if registration successful, False otherwise
        """
        # Validate hotkey
        is_valid, error = self.validate_hotkey(hotkey_string)
        if not is_valid:
            print(f"Invalid hotkey: {error}")
            return False

        # Unregister if already exists
        if hotkey_string in self.registered_hotkeys:
            self.unregister_hotkey(hotkey_string)

        keys = self.parse_hotkey(hotkey_string)

        # We need to monitor the main action key (last key in combination)
        action_key = keys[-1]
        modifier_keys = keys[:-1] if len(keys) > 1 else []

        hooks = []

        try:
            # Create press handler
            def press_handler(event):
                # Check if all modifier keys are pressed
                if all(keyboard.is_pressed(mod) for mod in modifier_keys):
                    on_press()

            # Create release handler
            def release_handler(event):
                # If any required key is no longer pressed, call release callback
                if not all(keyboard.is_pressed(key) for key in keys):
                    on_release()

            # Register press handler for action key
            press_hook = keyboard.on_press_key(action_key, press_handler, suppress=False)
            hooks.append(('press', action_key, press_hook))

            # Register release handlers for all keys in combination
            for key in keys:
                release_hook = keyboard.on_release_key(key, release_handler, suppress=False)
                hooks.append(('release', key, release_hook))

            # Store registration
            self.registered_hotkeys[hotkey_string] = (on_press, on_release)
            self.active_hooks[hotkey_string] = hooks

            print(f"Registered push-to-talk hotkey: {hotkey_string}")
            return True

        except Exception as e:
            print(f"Error registering hotkey {hotkey_string}: {e}")
            # Clean up any registered hooks
            for hook_type, key, hook in hooks:
                try:
                    keyboard.unhook(hook)
                except:
                    pass
            return False

    def register_hotkey(self, hotkey_string: str, callback: Callable,
                       trigger_on_release: bool = False) -> bool:
        """
        Register a simple hotkey (press and release together)

        Args:
            hotkey_string: Hotkey combination (e.g., "ctrl+shift+v")
            callback: Function to call when hotkey is triggered
            trigger_on_release: If True, trigger on key release instead of press

        Returns:
            True if registration successful, False otherwise
        """
        # Validate hotkey
        is_valid, error = self.validate_hotkey(hotkey_string)
        if not is_valid:
            print(f"Invalid hotkey: {error}")
            return False

        # Unregister if already exists
        if hotkey_string in self.registered_hotkeys:
            self.unregister_hotkey(hotkey_string)

        try:
            # Use keyboard library's add_hotkey for simple hotkeys
            keyboard.add_hotkey(
                hotkey_string.replace('+', ' + '),  # keyboard lib uses ' + ' separator
                callback,
                trigger_on_release=trigger_on_release
            )

            # Store registration
            self.registered_hotkeys[hotkey_string] = callback

            print(f"Registered hotkey: {hotkey_string}")
            return True

        except Exception as e:
            print(f"Error registering hotkey {hotkey_string}: {e}")
            return False

    def unregister_hotkey(self, hotkey_string: str) -> bool:
        """
        Unregister a hotkey

        Args:
            hotkey_string: Hotkey to unregister

        Returns:
            True if successful, False otherwise
        """
        if hotkey_string not in self.registered_hotkeys:
            return False

        try:
            # If we have active hooks (push-to-talk style), unhook them
            if hotkey_string in self.active_hooks:
                for hook_type, key, hook in self.active_hooks[hotkey_string]:
                    keyboard.unhook(hook)
                del self.active_hooks[hotkey_string]
            else:
                # Simple hotkey registered with add_hotkey
                keyboard.remove_hotkey(hotkey_string.replace('+', ' + '))

            del self.registered_hotkeys[hotkey_string]
            print(f"Unregistered hotkey: {hotkey_string}")
            return True

        except Exception as e:
            print(f"Error unregistering hotkey {hotkey_string}: {e}")
            return False

    def unregister_all(self):
        """Unregister all hotkeys"""
        hotkeys = list(self.registered_hotkeys.keys())
        for hotkey in hotkeys:
            self.unregister_hotkey(hotkey)

    def is_registered(self, hotkey_string: str) -> bool:
        """Check if a hotkey is registered"""
        return hotkey_string in self.registered_hotkeys

    def get_registered_hotkeys(self) -> List[str]:
        """Get list of all registered hotkeys"""
        return list(self.registered_hotkeys.keys())
