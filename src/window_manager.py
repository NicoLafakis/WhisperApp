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
