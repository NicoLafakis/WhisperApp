"""
Window Manager for WhisperApp
Handles window positioning and focus on Windows using win32 API
"""
import ctypes
from ctypes import wintypes
from typing import List, Tuple, Optional, Dict
import win32api
import win32con
import win32gui


class MonitorInfo:
    """Represents information about a monitor"""

    def __init__(self, handle, info):
        self.handle = handle
        self.info = info
        self.rect = info['Monitor']
        self.work_area = info['Work']
        self.is_primary = info['Flags'] == win32con.MONITORINFOF_PRIMARY

        # Calculate dimensions
        self.x = self.rect[0]
        self.y = self.rect[1]
        self.width = self.rect[2] - self.rect[0]
        self.height = self.rect[3] - self.rect[1]

        # Work area (excluding taskbar)
        self.work_x = self.work_area[0]
        self.work_y = self.work_area[1]
        self.work_width = self.work_area[2] - self.work_area[0]
        self.work_height = self.work_area[3] - self.work_area[1]

    def __repr__(self):
        return (f"MonitorInfo(handle={self.handle}, "
                f"rect=({self.x}, {self.y}, {self.width}, {self.height}), "
                f"primary={self.is_primary})")


class WindowManager:
    """Manages window positioning and focus"""

    def __init__(self):
        self.monitors: List[MonitorInfo] = []
        self.refresh_monitors()

    def refresh_monitors(self):
        """Refresh the list of available monitors"""
        self.monitors = []

        def monitor_enum_proc(hMonitor, hdcMonitor, lprcMonitor, dwData):
            info = win32api.GetMonitorInfo(hMonitor)
            self.monitors.append(MonitorInfo(hMonitor, info))
            return True

        # Enumerate all monitors
        win32api.EnumDisplayMonitors(None, None, monitor_enum_proc, 0)

        # Sort monitors: primary first, then by position (left to right)
        self.monitors.sort(key=lambda m: (not m.is_primary, m.x, m.y))

        print(f"Found {len(self.monitors)} monitor(s)")
        for i, monitor in enumerate(self.monitors, 1):
            print(f"  Monitor {i}: {monitor}")

    def get_monitor_count(self) -> int:
        """Get the number of monitors"""
        return len(self.monitors)

    def get_monitor(self, monitor_number: int) -> Optional[MonitorInfo]:
        """
        Get monitor by number (1-indexed)

        Args:
            monitor_number: Monitor number (1 = primary, 2 = second, etc.)

        Returns:
            MonitorInfo or None if monitor doesn't exist
        """
        if 1 <= monitor_number <= len(self.monitors):
            return self.monitors[monitor_number - 1]
        return None

    def get_quadrant_rect(self, monitor_number: int, quadrant: int) -> Optional[Tuple[int, int, int, int]]:
        """
        Get the rectangle for a specific quadrant on a monitor

        Quadrant layout:
        +-----+-----+
        |  1  |  2  |
        +-----+-----+
        |  3  |  4  |
        +-----+-----+

        Args:
            monitor_number: Monitor number (1-indexed)
            quadrant: Quadrant number (1-4)

        Returns:
            Tuple of (x, y, width, height) or None if invalid
        """
        monitor = self.get_monitor(monitor_number)
        if not monitor:
            return None

        if quadrant not in [1, 2, 3, 4]:
            return None

        # Use work area to avoid taskbar
        x = monitor.work_x
        y = monitor.work_y
        width = monitor.work_width
        height = monitor.work_height

        # Calculate half dimensions
        half_width = width // 2
        half_height = height // 2

        # Calculate quadrant position
        if quadrant == 1:  # Top-left
            return (x, y, half_width, half_height)
        elif quadrant == 2:  # Top-right
            return (x + half_width, y, half_width, half_height)
        elif quadrant == 3:  # Bottom-left
            return (x, y + half_height, half_width, half_height)
        elif quadrant == 4:  # Bottom-right
            return (x + half_width, y + half_height, half_width, half_height)

    def get_foreground_window(self) -> Optional[int]:
        """Get the handle of the currently focused window"""
        return win32gui.GetForegroundWindow()

    def get_window_title(self, hwnd: int) -> str:
        """Get the title of a window"""
        try:
            return win32gui.GetWindowText(hwnd)
        except:
            return ""

    def is_window_valid(self, hwnd: int) -> bool:
        """Check if a window is valid for manipulation"""
        if not hwnd or not win32gui.IsWindow(hwnd):
            return False

        # Check if window is visible
        if not win32gui.IsWindowVisible(hwnd):
            return False

        # Skip certain window types
        title = self.get_window_title(hwnd)
        if not title:
            return False

        # Skip Windows shell windows
        class_name = win32gui.GetClassName(hwnd)
        skip_classes = ['Shell_TrayWnd', 'DV2ControlHost', 'MsgrIMEWindowClass', 'SysShadow']
        if class_name in skip_classes:
            return False

        return True

    def move_window(self, hwnd: int, x: int, y: int, width: int, height: int) -> bool:
        """
        Move and resize a window

        Args:
            hwnd: Window handle
            x, y: Position
            width, height: Dimensions

        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if window is maximized or minimized
            placement = win32gui.GetWindowPlacement(hwnd)
            if placement[1] == win32con.SW_SHOWMAXIMIZED:
                # Restore the window first
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Move and resize the window
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                x, y, width, height,
                win32con.SWP_SHOWWINDOW
            )

            # Bring window to front
            win32gui.SetForegroundWindow(hwnd)

            return True

        except Exception as e:
            print(f"Error moving window: {e}")
            return False

    def move_window_to_quadrant(self, monitor_number: int, quadrant: int,
                               hwnd: Optional[int] = None) -> bool:
        """
        Move a window to a specific monitor quadrant

        Args:
            monitor_number: Monitor number (1-indexed)
            quadrant: Quadrant number (1-4)
            hwnd: Window handle (if None, uses foreground window)

        Returns:
            True if successful, False otherwise
        """
        # Get the window to move
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            print("Invalid or no foreground window")
            return False

        # Get quadrant rectangle
        rect = self.get_quadrant_rect(monitor_number, quadrant)
        if not rect:
            print(f"Invalid monitor {monitor_number} or quadrant {quadrant}")
            return False

        x, y, width, height = rect

        # Move the window
        success = self.move_window(hwnd, x, y, width, height)

        if success:
            title = self.get_window_title(hwnd)
            print(f"Moved '{title}' to monitor {monitor_number}, quadrant {quadrant}")

        return success

    def get_windows_at_quadrant(self, monitor_number: int, quadrant: int) -> List[int]:
        """
        Get all windows in a specific quadrant

        Args:
            monitor_number: Monitor number (1-indexed)
            quadrant: Quadrant number (1-4)

        Returns:
            List of window handles
        """
        rect = self.get_quadrant_rect(monitor_number, quadrant)
        if not rect:
            return []

        qx, qy, qw, qh = rect
        windows = []

        def enum_windows_callback(hwnd, lParam):
            if self.is_window_valid(hwnd):
                try:
                    # Get window rect
                    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
                    wx, wy = left, top
                    ww, wh = right - left, bottom - top

                    # Check if window center is in quadrant
                    center_x = wx + ww // 2
                    center_y = wy + wh // 2

                    if (qx <= center_x < qx + qw and
                        qy <= center_y < qy + qh):
                        windows.append(hwnd)

                except:
                    pass
            return True

        win32gui.EnumWindows(enum_windows_callback, None)
        return windows

    def focus_window_at_quadrant(self, monitor_number: int, quadrant: int) -> bool:
        """
        Focus a window at a specific quadrant

        Args:
            monitor_number: Monitor number (1-indexed)
            quadrant: Quadrant number (1-4)

        Returns:
            True if successful, False otherwise
        """
        windows = self.get_windows_at_quadrant(monitor_number, quadrant)

        if not windows:
            print(f"No windows found at monitor {monitor_number}, quadrant {quadrant}")
            return False

        # Focus the first window
        try:
            win32gui.SetForegroundWindow(windows[0])
            title = self.get_window_title(windows[0])
            print(f"Focused '{title}' at monitor {monitor_number}, quadrant {quadrant}")
            return True
        except Exception as e:
            print(f"Error focusing window: {e}")
            return False

    def get_monitor_layout_info(self) -> Dict[str, any]:
        """Get information about the monitor layout"""
        return {
            'count': len(self.monitors),
            'monitors': [
                {
                    'number': i + 1,
                    'x': m.x,
                    'y': m.y,
                    'width': m.width,
                    'height': m.height,
                    'is_primary': m.is_primary
                }
                for i, m in enumerate(self.monitors)
            ]
        }

    # ============= Basic Window Operations =============

    def minimize_window(self, hwnd: Optional[int] = None) -> bool:
        """
        Minimize a window

        Args:
            hwnd: Window handle (if None, uses foreground window)

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            title = self.get_window_title(hwnd)
            print(f"Minimized window: {title}")
            return True
        except Exception as e:
            print(f"Error minimizing window: {e}")
            return False

    def maximize_window(self, hwnd: Optional[int] = None) -> bool:
        """
        Maximize a window

        Args:
            hwnd: Window handle (if None, uses foreground window)

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MAXIMIZE)
            title = self.get_window_title(hwnd)
            print(f"Maximized window: {title}")
            return True
        except Exception as e:
            print(f"Error maximizing window: {e}")
            return False

    def restore_window(self, hwnd: Optional[int] = None) -> bool:
        """
        Restore a window (from minimized or maximized)

        Args:
            hwnd: Window handle (if None, uses foreground window)

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            title = self.get_window_title(hwnd)
            print(f"Restored window: {title}")
            return True
        except Exception as e:
            print(f"Error restoring window: {e}")
            return False

    def close_window(self, hwnd: Optional[int] = None) -> bool:
        """
        Close a window

        Args:
            hwnd: Window handle (if None, uses foreground window)

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        try:
            win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            title = self.get_window_title(hwnd)
            print(f"Closed window: {title}")
            return True
        except Exception as e:
            print(f"Error closing window: {e}")
            return False

    def set_window_always_on_top(self, hwnd: Optional[int] = None, on_top: bool = True) -> bool:
        """
        Set window always on top

        Args:
            hwnd: Window handle (if None, uses foreground window)
            on_top: True to set always on top, False to remove

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        try:
            flag = win32con.HWND_TOPMOST if on_top else win32con.HWND_NOTOPMOST
            win32gui.SetWindowPos(
                hwnd, flag, 0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE
            )
            title = self.get_window_title(hwnd)
            status = "on top" if on_top else "normal"
            print(f"Set window {status}: {title}")
            return True
        except Exception as e:
            print(f"Error setting window always on top: {e}")
            return False

    # ============= Window State Queries =============

    def is_window_minimized(self, hwnd: int) -> bool:
        """Check if window is minimized"""
        try:
            return win32gui.IsIconic(hwnd)
        except:
            return False

    def is_window_maximized(self, hwnd: int) -> bool:
        """Check if window is maximized"""
        try:
            placement = win32gui.GetWindowPlacement(hwnd)
            return placement[1] == win32con.SW_SHOWMAXIMIZED
        except:
            return False

    # ============= Advanced Window Operations =============

    def center_window(self, hwnd: Optional[int] = None, monitor_number: int = 1) -> bool:
        """
        Center a window on a monitor

        Args:
            hwnd: Window handle (if None, uses foreground window)
            monitor_number: Monitor to center on (1-indexed)

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        monitor = self.get_monitor(monitor_number)
        if not monitor:
            return False

        try:
            # Get current window size
            rect = win32gui.GetWindowRect(hwnd)
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]

            # Calculate center position
            x = monitor.work_x + (monitor.work_width - width) // 2
            y = monitor.work_y + (monitor.work_height - height) // 2

            return self.move_window(hwnd, x, y, width, height)

        except Exception as e:
            print(f"Error centering window: {e}")
            return False

    def move_to_next_monitor(self, hwnd: Optional[int] = None) -> bool:
        """
        Move window to next monitor

        Args:
            hwnd: Window handle (if None, uses foreground window)

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        if len(self.monitors) <= 1:
            print("Only one monitor available")
            return False

        try:
            # Get window position
            rect = win32gui.GetWindowRect(hwnd)
            center_x = (rect[0] + rect[2]) // 2
            center_y = (rect[1] + rect[3]) // 2

            # Find which monitor the window is on
            current_monitor = 0
            for i, monitor in enumerate(self.monitors):
                if (monitor.x <= center_x < monitor.x + monitor.width and
                    monitor.y <= center_y < monitor.y + monitor.height):
                    current_monitor = i
                    break

            # Get next monitor
            next_monitor_index = (current_monitor + 1) % len(self.monitors)
            next_monitor = self.monitors[next_monitor_index]

            # Calculate relative position in current monitor
            current = self.monitors[current_monitor]
            rel_x = (rect[0] - current.x) / current.width
            rel_y = (rect[1] - current.y) / current.height

            # Apply to next monitor
            width = rect[2] - rect[0]
            height = rect[3] - rect[1]
            new_x = int(next_monitor.x + rel_x * next_monitor.width)
            new_y = int(next_monitor.y + rel_y * next_monitor.height)

            return self.move_window(hwnd, new_x, new_y, width, height)

        except Exception as e:
            print(f"Error moving to next monitor: {e}")
            return False

    def snap_window(self, hwnd: Optional[int] = None, position: str = 'left') -> bool:
        """
        Snap window to screen edge (like Windows Snap)

        Args:
            hwnd: Window handle (if None, uses foreground window)
            position: 'left', 'right', 'top', 'bottom'

        Returns:
            True if successful
        """
        if hwnd is None:
            hwnd = self.get_foreground_window()

        if not self.is_window_valid(hwnd):
            return False

        # Get current monitor for the window
        try:
            rect = win32gui.GetWindowRect(hwnd)
            center_x = (rect[0] + rect[2]) // 2

            # Find monitor
            monitor = None
            for m in self.monitors:
                if m.x <= center_x < m.x + m.width:
                    monitor = m
                    break

            if not monitor:
                monitor = self.monitors[0]

            # Calculate snap position
            x = monitor.work_x
            y = monitor.work_y
            width = monitor.work_width
            height = monitor.work_height

            if position == 'left':
                width = width // 2
            elif position == 'right':
                x = x + width // 2
                width = width // 2
            elif position == 'top':
                height = height // 2
            elif position == 'bottom':
                y = y + height // 2
                height = height // 2

            return self.move_window(hwnd, x, y, width, height)

        except Exception as e:
            print(f"Error snapping window: {e}")
            return False

    def tile_windows_horizontal(self, hwnds: List[int]) -> bool:
        """
        Tile windows horizontally on current monitor

        Args:
            hwnds: List of window handles

        Returns:
            True if successful
        """
        if not hwnds:
            return False

        try:
            # Use primary monitor
            monitor = self.monitors[0]

            count = len(hwnds)
            width = monitor.work_width // count

            for i, hwnd in enumerate(hwnds):
                x = monitor.work_x + i * width
                self.move_window(hwnd, x, monitor.work_y, width, monitor.work_height)

            print(f"Tiled {count} windows horizontally")
            return True

        except Exception as e:
            print(f"Error tiling windows: {e}")
            return False

    def tile_windows_vertical(self, hwnds: List[int]) -> bool:
        """
        Tile windows vertically on current monitor

        Args:
            hwnds: List of window handles

        Returns:
            True if successful
        """
        if not hwnds:
            return False

        try:
            # Use primary monitor
            monitor = self.monitors[0]

            count = len(hwnds)
            height = monitor.work_height // count

            for i, hwnd in enumerate(hwnds):
                y = monitor.work_y + i * height
                self.move_window(hwnd, monitor.work_x, y, monitor.work_width, height)

            print(f"Tiled {count} windows vertically")
            return True

        except Exception as e:
            print(f"Error tiling windows: {e}")
            return False
