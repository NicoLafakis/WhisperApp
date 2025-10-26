"""
Application Controller for WhisperApp
Handles launching, switching, and managing applications
"""
import subprocess
import os
import psutil
import win32gui
import win32con
import win32process
from typing import Optional, List, Dict
from pathlib import Path


class ApplicationController:
    """Controls application launching, switching, and process management"""

    def __init__(self):
        # Common application paths - can be extended
        self.app_paths = {
            'chrome': r'C:\Program Files\Google\Chrome\Application\chrome.exe',
            'firefox': r'C:\Program Files\Mozilla Firefox\firefox.exe',
            'edge': r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
            'notepad': r'C:\Windows\System32\notepad.exe',
            'calculator': r'C:\Windows\System32\calc.exe',
            'explorer': r'C:\Windows\explorer.exe',
            'cmd': r'C:\Windows\System32\cmd.exe',
            'powershell': r'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe',
            'paint': r'C:\Windows\System32\mspaint.exe',
            'wordpad': r'C:\Program Files\Windows NT\Accessories\wordpad.exe',
        }

        # Application name mappings for finding windows
        self.app_window_patterns = {
            'chrome': ['Chrome', 'Google Chrome'],
            'firefox': ['Firefox', 'Mozilla Firefox'],
            'edge': ['Edge', 'Microsoft Edge'],
            'notepad': ['Notepad', 'Untitled - Notepad'],
            'calculator': ['Calculator'],
            'explorer': ['File Explorer', 'Windows Explorer'],
            'vscode': ['Visual Studio Code', 'VS Code'],
            'code': ['Visual Studio Code', 'VS Code'],
            'slack': ['Slack'],
            'teams': ['Microsoft Teams', 'Teams'],
            'outlook': ['Outlook'],
            'word': ['Microsoft Word', 'Word'],
            'excel': ['Microsoft Excel', 'Excel'],
            'powerpoint': ['Microsoft PowerPoint', 'PowerPoint'],
            'spotify': ['Spotify'],
            'discord': ['Discord'],
        }

    def launch_application(self, app_name: str, arguments: str = "") -> bool:
        """
        Launch an application

        Args:
            app_name: Name of application to launch
            arguments: Command line arguments

        Returns:
            True if launched successfully
        """
        app_name_lower = app_name.lower()

        try:
            # Try predefined path first
            if app_name_lower in self.app_paths:
                app_path = self.app_paths[app_name_lower]
                if os.path.exists(app_path):
                    if arguments:
                        subprocess.Popen([app_path, arguments])
                    else:
                        subprocess.Popen([app_path])
                    print(f"Launched {app_name} from {app_path}")
                    return True

            # Try to launch by name (if in PATH or registered)
            try:
                if arguments:
                    subprocess.Popen([app_name, arguments])
                else:
                    subprocess.Popen([app_name])
                print(f"Launched {app_name} by name")
                return True
            except:
                pass

            # Try using os.startfile for registered file types/apps
            try:
                os.startfile(app_name)
                print(f"Launched {app_name} using startfile")
                return True
            except:
                pass

            print(f"Could not find application: {app_name}")
            return False

        except Exception as e:
            print(f"Error launching {app_name}: {e}")
            return False

    def open_url(self, url: str) -> bool:
        """
        Open URL in default browser

        Args:
            url: URL to open

        Returns:
            True if successful
        """
        try:
            # Ensure URL has protocol
            if not url.startswith(('http://', 'https://')):
                url = 'https://' + url

            os.startfile(url)
            print(f"Opened URL: {url}")
            return True
        except Exception as e:
            print(f"Error opening URL {url}: {e}")
            return False

    def find_windows_by_title(self, title_pattern: str) -> List[int]:
        """
        Find window handles by title pattern

        Args:
            title_pattern: Pattern to match in window title

        Returns:
            List of window handles
        """
        matching_windows = []
        title_pattern_lower = title_pattern.lower()

        def enum_callback(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd):
                window_title = win32gui.GetWindowText(hwnd)
                if window_title and title_pattern_lower in window_title.lower():
                    matching_windows.append(hwnd)
            return True

        win32gui.EnumWindows(enum_callback, None)
        return matching_windows

    def find_windows_by_process_name(self, process_name: str) -> List[int]:
        """
        Find window handles by process name

        Args:
            process_name: Name of process (e.g., 'chrome.exe')

        Returns:
            List of window handles
        """
        matching_windows = []
        process_name_lower = process_name.lower()

        if not process_name_lower.endswith('.exe'):
            process_name_lower += '.exe'

        def enum_callback(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    process = psutil.Process(pid)
                    if process.name().lower() == process_name_lower:
                        matching_windows.append(hwnd)
                except:
                    pass
            return True

        win32gui.EnumWindows(enum_callback, None)
        return matching_windows

    def find_application_windows(self, app_name: str) -> List[int]:
        """
        Find windows for a specific application

        Args:
            app_name: Application name

        Returns:
            List of window handles
        """
        app_name_lower = app_name.lower()

        # Try using window patterns first
        if app_name_lower in self.app_window_patterns:
            patterns = self.app_window_patterns[app_name_lower]
            windows = []
            for pattern in patterns:
                windows.extend(self.find_windows_by_title(pattern))
            if windows:
                return windows

        # Try finding by process name
        windows = self.find_windows_by_process_name(app_name)
        if windows:
            return windows

        # Fallback to title search
        return self.find_windows_by_title(app_name)

    def switch_to_application(self, app_name: str) -> bool:
        """
        Switch focus to an application

        Args:
            app_name: Application name

        Returns:
            True if successful
        """
        windows = self.find_application_windows(app_name)

        if not windows:
            print(f"No windows found for {app_name}")
            return False

        try:
            # Focus the first window found
            hwnd = windows[0]

            # If minimized, restore it
            if win32gui.IsIconic(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

            # Bring to foreground
            win32gui.SetForegroundWindow(hwnd)

            title = win32gui.GetWindowText(hwnd)
            print(f"Switched to {app_name}: {title}")
            return True

        except Exception as e:
            print(f"Error switching to {app_name}: {e}")
            return False

    def close_application(self, app_name: str, force: bool = False) -> bool:
        """
        Close an application

        Args:
            app_name: Application name
            force: If True, force kill the process

        Returns:
            True if successful
        """
        if force:
            return self.kill_application(app_name)

        # Try to close windows gracefully
        windows = self.find_application_windows(app_name)

        if not windows:
            print(f"No windows found for {app_name}")
            return False

        try:
            for hwnd in windows:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)

            print(f"Closed {len(windows)} window(s) for {app_name}")
            return True

        except Exception as e:
            print(f"Error closing {app_name}: {e}")
            return False

    def kill_application(self, app_name: str) -> bool:
        """
        Force kill an application process

        Args:
            app_name: Application name

        Returns:
            True if successful
        """
        app_name_lower = app_name.lower()
        if not app_name_lower.endswith('.exe'):
            app_name_lower += '.exe'

        killed_count = 0

        try:
            for proc in psutil.process_iter(['name']):
                try:
                    if proc.info['name'].lower() == app_name_lower:
                        proc.kill()
                        killed_count += 1
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

            if killed_count > 0:
                print(f"Killed {killed_count} process(es) for {app_name}")
                return True
            else:
                print(f"No processes found for {app_name}")
                return False

        except Exception as e:
            print(f"Error killing {app_name}: {e}")
            return False

    def get_running_applications(self) -> List[Dict[str, any]]:
        """
        Get list of running applications with windows

        Returns:
            List of dicts with app info
        """
        apps = {}

        def enum_callback(hwnd, lParam):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        process = psutil.Process(pid)
                        proc_name = process.name()

                        if proc_name not in apps:
                            apps[proc_name] = {
                                'name': proc_name,
                                'windows': [],
                                'pid': pid
                            }

                        apps[proc_name]['windows'].append({
                            'hwnd': hwnd,
                            'title': title
                        })
                    except:
                        pass
            return True

        win32gui.EnumWindows(enum_callback, None)
        return list(apps.values())

    def is_application_running(self, app_name: str) -> bool:
        """
        Check if an application is running

        Args:
            app_name: Application name

        Returns:
            True if running
        """
        windows = self.find_application_windows(app_name)
        return len(windows) > 0

    def register_application_path(self, app_name: str, app_path: str):
        """
        Register a custom application path

        Args:
            app_name: Application name
            app_path: Full path to executable
        """
        self.app_paths[app_name.lower()] = app_path
        print(f"Registered {app_name}: {app_path}")

    def register_window_pattern(self, app_name: str, patterns: List[str]):
        """
        Register window title patterns for an application

        Args:
            app_name: Application name
            patterns: List of title patterns
        """
        self.app_window_patterns[app_name.lower()] = patterns
        print(f"Registered window patterns for {app_name}: {patterns}")
