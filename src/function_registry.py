"""
Function Registry for JARVIS
Defines all available functions that GPT can call for PC control
Maps to existing controller capabilities
"""
import json
from typing import Dict, List, Any, Callable, Optional
from pathlib import Path
from datetime import datetime
import win32gui
import win32process
import psutil


class FunctionRegistry:
    """
    Registry of all functions available to the AI assistant
    Provides function definitions for GPT and execution handlers
    """

    def __init__(self, window_manager, app_controller, automation_controller,
                 audio_controller, clipboard_controller, file_controller):
        """
        Initialize function registry with all controllers

        Args:
            window_manager: WindowManager instance
            app_controller: ApplicationController instance
            automation_controller: AutomationController instance
            audio_controller: AudioController instance
            clipboard_controller: ClipboardController instance
            file_controller: FileController instance
        """
        self.window_manager = window_manager
        self.app_controller = app_controller
        self.automation_controller = automation_controller
        self.audio_controller = audio_controller
        self.clipboard_controller = clipboard_controller
        self.file_controller = file_controller

        # Map function names to handlers
        self.function_handlers = self._build_function_handlers()

    def get_function_definitions(self) -> List[Dict[str, Any]]:
        """
        Get function definitions for GPT function calling

        Returns:
            List of function definition dictionaries
        """
        return [
            # Window Management Functions
            {
                "name": "move_window",
                "description": "Move the active window to a specific monitor and position (top, bottom, or full screen). Use this when user wants to move, position, or relocate windows.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "monitor": {
                            "type": "integer",
                            "description": "Monitor number (1, 2, or 3). Monitor 1 is left vertical, Monitor 3 is center horizontal, Monitor 2 is right vertical."
                        },
                        "position": {
                            "type": "string",
                            "enum": ["top", "bottom", "full"],
                            "description": "Position on monitor: 'top' for upper half, 'bottom' for lower half, 'full' for fullscreen/maximize"
                        },
                        "window_title": {
                            "type": "string",
                            "description": "Optional: Specific window title or app name to move. If not provided, moves the currently active window."
                        }
                    },
                    "required": ["monitor", "position"]
                }
            },
            {
                "name": "minimize_window",
                "description": "Minimize the current active window",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "maximize_window",
                "description": "Maximize the current active window to fill the entire screen",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "restore_window",
                "description": "Restore a minimized or maximized window to its normal size",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "center_window",
                "description": "Center the active window on a specific monitor",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "monitor": {
                            "type": "integer",
                            "description": "Monitor number to center on (default: 1)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "snap_window",
                "description": "Snap window to screen edge (Windows Snap feature)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["left", "right", "top", "bottom"],
                            "description": "Direction to snap window"
                        }
                    },
                    "required": ["direction"]
                }
            },
            {
                "name": "close_window",
                "description": "Close the currently active window",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_window_info",
                "description": "Get information about the currently active window",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "move_to_next_monitor",
                "description": "Move the active window to the next monitor",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Application Control Functions
            {
                "name": "launch_application",
                "description": "Launch or open an application. Supports common apps like Chrome, Firefox, VS Code, Notepad, Calculator, Spotify, etc.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Application name (e.g., 'chrome', 'notepad', 'vscode', 'calculator', 'spotify')"
                        },
                        "arguments": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Optional command-line arguments"
                        }
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "switch_to_application",
                "description": "Switch focus to a running application by name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Application name or window title to switch to"
                        }
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "close_application",
                "description": "Close an application by name",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "app_name": {
                            "type": "string",
                            "description": "Application name to close"
                        }
                    },
                    "required": ["app_name"]
                }
            },
            {
                "name": "get_running_applications",
                "description": "Get a list of all currently running applications",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # System Control Functions
            {
                "name": "set_volume",
                "description": "Set system master volume to a specific level",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "level": {
                            "type": "integer",
                            "description": "Volume level (0-100)",
                            "minimum": 0,
                            "maximum": 100
                        }
                    },
                    "required": ["level"]
                }
            },
            {
                "name": "volume_up",
                "description": "Increase system volume by 10%",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "volume_down",
                "description": "Decrease system volume by 10%",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "mute",
                "description": "Mute system audio",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "unmute",
                "description": "Unmute system audio",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "toggle_mute",
                "description": "Toggle system mute on/off",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_volume",
                "description": "Get current system volume level",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Automation Functions
            {
                "name": "type_text",
                "description": "Type text using the keyboard (useful for dictation)",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to type"
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "press_keys",
                "description": "Press a key combination (e.g., 'ctrl+s', 'alt+tab')",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key_combo": {
                            "type": "string",
                            "description": "Key combination to press (e.g., 'ctrl+s', 'alt+f4', 'win+d')"
                        }
                    },
                    "required": ["key_combo"]
                }
            },
            {
                "name": "click_mouse",
                "description": "Click the mouse at current position",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "button": {
                            "type": "string",
                            "enum": ["left", "right", "middle"],
                            "description": "Mouse button to click (default: left)"
                        },
                        "double": {
                            "type": "boolean",
                            "description": "Whether to double-click (default: false)"
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "scroll",
                "description": "Scroll the mouse wheel",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "direction": {
                            "type": "string",
                            "enum": ["up", "down"],
                            "description": "Scroll direction"
                        },
                        "amount": {
                            "type": "integer",
                            "description": "Number of scroll steps (default: 3)"
                        }
                    },
                    "required": ["direction"]
                }
            },

            # File System Functions
            {
                "name": "open_folder",
                "description": "Open a folder in Windows Explorer",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Folder path or special folder name (Desktop, Documents, Downloads, Pictures, Videos, Music, Home)"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "create_folder",
                "description": "Create a new folder",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Path where to create the folder"
                        }
                    },
                    "required": ["path"]
                }
            },
            {
                "name": "search_files",
                "description": "Search for files by name pattern",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search pattern or filename"
                        },
                        "directory": {
                            "type": "string",
                            "description": "Directory to search in (default: Home)"
                        }
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "open_file",
                "description": "Open a file with its default application",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full path to the file"
                        }
                    },
                    "required": ["path"]
                }
            },

            # Clipboard Functions
            {
                "name": "copy_to_clipboard",
                "description": "Copy text to the clipboard",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "Text to copy"
                        }
                    },
                    "required": ["text"]
                }
            },
            {
                "name": "get_clipboard",
                "description": "Get current clipboard contents",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "paste_from_clipboard",
                "description": "Paste from clipboard at current cursor position",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },

            # Information Query Functions
            {
                "name": "get_time",
                "description": "Get the current time",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_date",
                "description": "Get the current date",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_monitor_info",
                "description": "Get information about all connected monitors",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": "get_system_info",
                "description": "Get system information (CPU, RAM, disk usage)",
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            }
        ]

    def _build_function_handlers(self) -> Dict[str, Callable]:
        """Build mapping of function names to handler methods"""
        return {
            # Window Management
            "move_window": self._handle_move_window,
            "minimize_window": self._handle_minimize_window,
            "maximize_window": self._handle_maximize_window,
            "restore_window": self._handle_restore_window,
            "center_window": self._handle_center_window,
            "snap_window": self._handle_snap_window,
            "close_window": self._handle_close_window,
            "get_window_info": self._handle_get_window_info,
            "move_to_next_monitor": self._handle_move_to_next_monitor,

            # Application Control
            "launch_application": self._handle_launch_application,
            "switch_to_application": self._handle_switch_to_application,
            "close_application": self._handle_close_application,
            "get_running_applications": self._handle_get_running_applications,

            # System Control
            "set_volume": self._handle_set_volume,
            "volume_up": self._handle_volume_up,
            "volume_down": self._handle_volume_down,
            "mute": self._handle_mute,
            "unmute": self._handle_unmute,
            "toggle_mute": self._handle_toggle_mute,
            "get_volume": self._handle_get_volume,

            # Automation
            "type_text": self._handle_type_text,
            "press_keys": self._handle_press_keys,
            "click_mouse": self._handle_click_mouse,
            "scroll": self._handle_scroll,

            # File System
            "open_folder": self._handle_open_folder,
            "create_folder": self._handle_create_folder,
            "search_files": self._handle_search_files,
            "open_file": self._handle_open_file,

            # Clipboard
            "copy_to_clipboard": self._handle_copy_to_clipboard,
            "get_clipboard": self._handle_get_clipboard,
            "paste_from_clipboard": self._handle_paste_from_clipboard,

            # Information
            "get_time": self._handle_get_time,
            "get_date": self._handle_get_date,
            "get_monitor_info": self._handle_get_monitor_info,
            "get_system_info": self._handle_get_system_info,
        }

    def execute_function(self, function_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a function by name with given arguments

        Args:
            function_name: Name of function to execute
            arguments: Dictionary of arguments

        Returns:
            Result dictionary with success status and data/error message
        """
        handler = self.function_handlers.get(function_name)
        if not handler:
            return {
                "success": False,
                "error": f"Unknown function: {function_name}"
            }

        try:
            return handler(arguments)
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    # Window Management Handlers
    def _handle_move_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        monitor = args.get("monitor", 1)
        position = args.get("position", "full")
        window_title = args.get("window_title")

        try:
            # Use the new simplified positioning system
            success = self.window_manager.move_window_to_position(monitor, position)
            window_name = self.window_manager.get_window_title(
                self.window_manager.get_foreground_window()
            )

            return {
                "success": success,
                "window_title": window_name,
                "monitor": monitor,
                "position": position
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _handle_minimize_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.window_manager.minimize_window()
        return {"success": success}

    def _handle_maximize_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.window_manager.maximize_window()
        return {"success": success}

    def _handle_restore_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.window_manager.restore_window()
        return {"success": success}

    def _handle_center_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        monitor = args.get("monitor", 1)
        success = self.window_manager.center_window(monitor)
        return {"success": success, "monitor": monitor}

    def _handle_snap_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        direction = args.get("direction", "left")
        success = self.window_manager.snap_window(direction)
        return {"success": success, "direction": direction}

    def _handle_close_window(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.window_manager.close_window()
        return {"success": success}

    def _handle_get_window_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        hwnd = self.window_manager.get_foreground_window()
        title = self.window_manager.get_window_title(hwnd)
        is_maximized = self.window_manager.is_window_maximized(hwnd)
        is_minimized = self.window_manager.is_window_minimized(hwnd)

        return {
            "success": True,
            "title": title,
            "maximized": is_maximized,
            "minimized": is_minimized
        }

    def _handle_move_to_next_monitor(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.window_manager.move_to_next_monitor()
        return {"success": success}

    # Application Control Handlers
    def _handle_launch_application(self, args: Dict[str, Any]) -> Dict[str, Any]:
        app_name = args.get("app_name", "")
        arguments = args.get("arguments", [])
        # Convert list arguments to string if needed
        args_str = " ".join(arguments) if isinstance(arguments, list) else str(arguments)
        success = self.app_controller.launch_application(app_name, args_str if args_str else "")
        return {"success": success, "app_name": app_name}

    def _handle_switch_to_application(self, args: Dict[str, Any]) -> Dict[str, Any]:
        app_name = args.get("app_name", "")
        success = self.app_controller.switch_to_application(app_name)
        return {"success": success, "app_name": app_name}

    def _handle_close_application(self, args: Dict[str, Any]) -> Dict[str, Any]:
        app_name = args.get("app_name", "")
        success = self.app_controller.close_application(app_name, force=False)
        return {"success": success, "app_name": app_name}

    def _handle_get_running_applications(self, args: Dict[str, Any]) -> Dict[str, Any]:
        import win32gui
        import win32process
        import psutil

        apps = []
        def enum_windows_callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        process = psutil.Process(pid)
                        apps.append({
                            "title": title,
                            "process": process.name()
                        })
                    except:
                        pass
            return True

        win32gui.EnumWindows(enum_windows_callback, None)

        # Remove duplicates
        unique_apps = []
        seen = set()
        for app in apps:
            if app["title"] not in seen:
                seen.add(app["title"])
                unique_apps.append(app)

        return {"success": True, "applications": unique_apps[:20]}  # Limit to 20

    # System Control Handlers
    def _handle_set_volume(self, args: Dict[str, Any]) -> Dict[str, Any]:
        level = args.get("level", 50)
        success = self.audio_controller.set_master_volume(level)
        return {"success": success, "level": level}

    def _handle_volume_up(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.audio_controller.volume_up()
        new_level = self.audio_controller.get_master_volume()
        return {"success": success, "new_level": int(new_level)}

    def _handle_volume_down(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.audio_controller.volume_down()
        new_level = self.audio_controller.get_master_volume()
        return {"success": success, "new_level": int(new_level)}

    def _handle_mute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.audio_controller.mute()
        return {"success": success}

    def _handle_unmute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.audio_controller.unmute()
        return {"success": success}

    def _handle_toggle_mute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        success = self.audio_controller.toggle_mute()
        is_muted = self.audio_controller.is_muted()
        return {"success": success, "muted": is_muted}

    def _handle_get_volume(self, args: Dict[str, Any]) -> Dict[str, Any]:
        level = self.audio_controller.get_master_volume()
        return {"success": True, "level": int(level)}

    # Automation Handlers
    def _handle_type_text(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text", "")
        success = self.automation_controller.type_text(text)
        return {"success": success, "text_length": len(text)}

    def _handle_press_keys(self, args: Dict[str, Any]) -> Dict[str, Any]:
        key_combo = args.get("key_combo", "")
        success = self.automation_controller.press_hotkey(key_combo)
        return {"success": success, "key_combo": key_combo}

    def _handle_click_mouse(self, args: Dict[str, Any]) -> Dict[str, Any]:
        button = args.get("button", "left")
        double = args.get("double", False)

        if double:
            success = self.automation_controller.double_click()
        elif button == "right":
            success = self.automation_controller.right_click()
        else:
            success = self.automation_controller.click()

        return {"success": success, "button": button, "double": double}

    def _handle_scroll(self, args: Dict[str, Any]) -> Dict[str, Any]:
        direction = args.get("direction", "up")
        amount = args.get("amount", 3)
        success = self.automation_controller.scroll(direction, amount)
        return {"success": success, "direction": direction, "amount": amount}

    # File System Handlers
    def _handle_open_folder(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path", "")
        success = self.file_controller.open_folder(path)
        return {"success": success, "path": path}

    def _handle_create_folder(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path", "")
        success = self.file_controller.create_folder(path)
        return {"success": success, "path": path}

    def _handle_search_files(self, args: Dict[str, Any]) -> Dict[str, Any]:
        query = args.get("query", "")
        directory = args.get("directory", str(Path.home()))
        # Use find_files with the query as the pattern
        results = self.file_controller.find_files(directory, pattern=query, recursive=True)
        return {"success": True, "results": results[:10]}  # Limit to 10 results

    def _handle_open_file(self, args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path", "")
        success = self.file_controller.open_file(path)
        return {"success": success, "path": path}

    # Clipboard Handlers
    def _handle_copy_to_clipboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = args.get("text", "")
        success = self.clipboard_controller.copy_text(text)
        return {"success": success}

    def _handle_get_clipboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
        text = self.clipboard_controller.paste_text()
        return {"success": text is not None, "text": text if text else ""}

    def _handle_paste_from_clipboard(self, args: Dict[str, Any]) -> Dict[str, Any]:
        # Trigger a paste action using automation controller
        success = self.automation_controller.paste()
        return {"success": success}

    # Information Handlers
    def _handle_get_time(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from datetime import datetime
        now = datetime.now()
        return {
            "success": True,
            "time": now.strftime("%I:%M %p"),
            "time_24h": now.strftime("%H:%M")
        }

    def _handle_get_date(self, args: Dict[str, Any]) -> Dict[str, Any]:
        from datetime import datetime
        now = datetime.now()
        return {
            "success": True,
            "date": now.strftime("%B %d, %Y"),
            "day_of_week": now.strftime("%A")
        }

    def _handle_get_monitor_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        monitors = []
        for i, monitor in enumerate(self.window_manager.monitors, 1):
            monitors.append({
                "number": i,
                "width": monitor.work_width,
                "height": monitor.work_height,
                "is_primary": monitor.is_primary
            })

        return {"success": True, "monitors": monitors}

    def _handle_get_system_info(self, args: Dict[str, Any]) -> Dict[str, Any]:
        import psutil

        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')

        return {
            "success": True,
            "cpu_usage": f"{cpu_percent}%",
            "memory_usage": f"{memory.percent}%",
            "memory_available": f"{memory.available / (1024**3):.1f} GB",
            "disk_usage": f"{disk.percent}%",
            "disk_free": f"{disk.free / (1024**3):.1f} GB"
        }
