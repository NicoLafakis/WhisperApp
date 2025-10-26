"""
File Controller for WhisperApp
Handles file and folder operations
"""
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Dict
import win32api
import win32con


class FileController:
    """Controls file and folder operations"""

    def __init__(self):
        # Common folder paths
        self.special_folders = {
            'desktop': Path.home() / 'Desktop',
            'documents': Path.home() / 'Documents',
            'downloads': Path.home() / 'Downloads',
            'pictures': Path.home() / 'Pictures',
            'videos': Path.home() / 'Videos',
            'music': Path.home() / 'Music',
            'home': Path.home(),
            'temp': Path(os.getenv('TEMP', 'C:/Windows/Temp')),
        }

    # ============= Folder Operations =============

    def open_folder(self, folder_path: str) -> bool:
        """
        Open folder in Windows Explorer

        Args:
            folder_path: Path to folder or special folder name

        Returns:
            True if successful
        """
        try:
            # Check if it's a special folder name
            folder_path_lower = folder_path.lower()
            if folder_path_lower in self.special_folders:
                path = self.special_folders[folder_path_lower]
            else:
                path = Path(folder_path)

            if path.exists() and path.is_dir():
                os.startfile(str(path))
                print(f"Opened folder: {path}")
                return True
            else:
                print(f"Folder does not exist: {path}")
                return False

        except Exception as e:
            print(f"Error opening folder {folder_path}: {e}")
            return False

    def create_folder(self, folder_path: str) -> bool:
        """
        Create a new folder

        Args:
            folder_path: Path for new folder

        Returns:
            True if successful
        """
        try:
            path = Path(folder_path)
            path.mkdir(parents=True, exist_ok=True)
            print(f"Created folder: {path}")
            return True
        except Exception as e:
            print(f"Error creating folder {folder_path}: {e}")
            return False

    def delete_folder(self, folder_path: str, recursive: bool = False) -> bool:
        """
        Delete a folder

        Args:
            folder_path: Path to folder
            recursive: If True, delete all contents

        Returns:
            True if successful
        """
        try:
            path = Path(folder_path)

            if not path.exists():
                print(f"Folder does not exist: {path}")
                return False

            if recursive:
                shutil.rmtree(str(path))
            else:
                path.rmdir()  # Only works if empty

            print(f"Deleted folder: {path}")
            return True

        except Exception as e:
            print(f"Error deleting folder {folder_path}: {e}")
            return False

    def rename_folder(self, old_path: str, new_name: str) -> bool:
        """
        Rename a folder

        Args:
            old_path: Current folder path
            new_name: New folder name (not full path)

        Returns:
            True if successful
        """
        try:
            old = Path(old_path)
            new = old.parent / new_name

            old.rename(new)
            print(f"Renamed folder: {old} -> {new}")
            return True

        except Exception as e:
            print(f"Error renaming folder: {e}")
            return False

    def list_folder_contents(self, folder_path: str) -> List[str]:
        """
        List contents of a folder

        Args:
            folder_path: Path to folder

        Returns:
            List of file/folder names
        """
        try:
            path = Path(folder_path)

            if not path.exists() or not path.is_dir():
                return []

            return [item.name for item in path.iterdir()]

        except Exception as e:
            print(f"Error listing folder contents: {e}")
            return []

    # ============= File Operations =============

    def open_file(self, file_path: str) -> bool:
        """
        Open file with default application

        Args:
            file_path: Path to file

        Returns:
            True if successful
        """
        try:
            path = Path(file_path)

            if path.exists() and path.is_file():
                os.startfile(str(path))
                print(f"Opened file: {path}")
                return True
            else:
                print(f"File does not exist: {path}")
                return False

        except Exception as e:
            print(f"Error opening file {file_path}: {e}")
            return False

    def create_file(self, file_path: str, content: str = "") -> bool:
        """
        Create a new file

        Args:
            file_path: Path for new file
            content: Initial file content

        Returns:
            True if successful
        """
        try:
            path = Path(file_path)

            # Create parent directories if needed
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)

            print(f"Created file: {path}")
            return True

        except Exception as e:
            print(f"Error creating file {file_path}: {e}")
            return False

    def delete_file(self, file_path: str) -> bool:
        """
        Delete a file

        Args:
            file_path: Path to file

        Returns:
            True if successful
        """
        try:
            path = Path(file_path)

            if path.exists() and path.is_file():
                path.unlink()
                print(f"Deleted file: {path}")
                return True
            else:
                print(f"File does not exist: {path}")
                return False

        except Exception as e:
            print(f"Error deleting file {file_path}: {e}")
            return False

    def rename_file(self, old_path: str, new_name: str) -> bool:
        """
        Rename a file

        Args:
            old_path: Current file path
            new_name: New file name (not full path)

        Returns:
            True if successful
        """
        try:
            old = Path(old_path)
            new = old.parent / new_name

            old.rename(new)
            print(f"Renamed file: {old} -> {new}")
            return True

        except Exception as e:
            print(f"Error renaming file: {e}")
            return False

    def copy_file(self, source: str, destination: str) -> bool:
        """
        Copy a file

        Args:
            source: Source file path
            destination: Destination path

        Returns:
            True if successful
        """
        try:
            shutil.copy2(source, destination)
            print(f"Copied file: {source} -> {destination}")
            return True
        except Exception as e:
            print(f"Error copying file: {e}")
            return False

    def move_file(self, source: str, destination: str) -> bool:
        """
        Move a file

        Args:
            source: Source file path
            destination: Destination path

        Returns:
            True if successful
        """
        try:
            shutil.move(source, destination)
            print(f"Moved file: {source} -> {destination}")
            return True
        except Exception as e:
            print(f"Error moving file: {e}")
            return False

    # ============= Search Operations =============

    def find_files(self, folder_path: str, pattern: str = "*", recursive: bool = True) -> List[str]:
        """
        Find files matching pattern

        Args:
            folder_path: Folder to search in
            pattern: File pattern (e.g., "*.txt", "*.py")
            recursive: Search subdirectories

        Returns:
            List of matching file paths
        """
        try:
            path = Path(folder_path)

            if not path.exists() or not path.is_dir():
                return []

            if recursive:
                matches = list(path.rglob(pattern))
            else:
                matches = list(path.glob(pattern))

            return [str(m) for m in matches if m.is_file()]

        except Exception as e:
            print(f"Error finding files: {e}")
            return []

    def search_file_content(self, folder_path: str, search_text: str,
                           file_pattern: str = "*.txt") -> List[Dict[str, any]]:
        """
        Search for text within files

        Args:
            folder_path: Folder to search in
            search_text: Text to search for
            file_pattern: File pattern to search

        Returns:
            List of dicts with file path and line numbers
        """
        results = []

        try:
            files = self.find_files(folder_path, file_pattern, recursive=True)

            for file_path in files:
                try:
                    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                        matching_lines = []

                        for i, line in enumerate(lines, 1):
                            if search_text.lower() in line.lower():
                                matching_lines.append({
                                    'line_number': i,
                                    'content': line.strip()
                                })

                        if matching_lines:
                            results.append({
                                'file': file_path,
                                'matches': matching_lines
                            })

                except:
                    pass  # Skip files that can't be read

        except Exception as e:
            print(f"Error searching file content: {e}")

        return results

    # ============= File Info =============

    def get_file_info(self, file_path: str) -> Optional[Dict[str, any]]:
        """
        Get information about a file

        Args:
            file_path: Path to file

        Returns:
            Dict with file information or None
        """
        try:
            path = Path(file_path)

            if not path.exists():
                return None

            stats = path.stat()

            return {
                'name': path.name,
                'path': str(path.absolute()),
                'size': stats.st_size,
                'size_mb': round(stats.st_size / (1024 * 1024), 2),
                'created': stats.st_ctime,
                'modified': stats.st_mtime,
                'is_file': path.is_file(),
                'is_dir': path.is_dir(),
                'extension': path.suffix
            }

        except Exception as e:
            print(f"Error getting file info: {e}")
            return None

    def get_folder_size(self, folder_path: str) -> int:
        """
        Get total size of folder and contents

        Args:
            folder_path: Path to folder

        Returns:
            Size in bytes
        """
        try:
            path = Path(folder_path)
            total_size = 0

            for item in path.rglob('*'):
                if item.is_file():
                    total_size += item.stat().st_size

            return total_size

        except Exception as e:
            print(f"Error getting folder size: {e}")
            return 0

    # ============= Special Folder Access =============

    def get_special_folder(self, folder_name: str) -> Optional[str]:
        """
        Get path to special folder

        Args:
            folder_name: Name of special folder

        Returns:
            Path string or None
        """
        folder_name_lower = folder_name.lower()

        if folder_name_lower in self.special_folders:
            return str(self.special_folders[folder_name_lower])

        return None

    def open_desktop(self) -> bool:
        """Open Desktop folder"""
        return self.open_folder('desktop')

    def open_downloads(self) -> bool:
        """Open Downloads folder"""
        return self.open_folder('downloads')

    def open_documents(self) -> bool:
        """Open Documents folder"""
        return self.open_folder('documents')

    # ============= File Operations via Explorer =============

    def show_in_explorer(self, file_path: str) -> bool:
        """
        Show file in Windows Explorer and select it

        Args:
            file_path: Path to file

        Returns:
            True if successful
        """
        try:
            path = Path(file_path).absolute()
            subprocess.run(['explorer', '/select,', str(path)])
            print(f"Showed in Explorer: {path}")
            return True
        except Exception as e:
            print(f"Error showing in explorer: {e}")
            return False

    def get_file_properties(self, file_path: str) -> bool:
        """
        Show Windows file properties dialog

        Args:
            file_path: Path to file

        Returns:
            True if successful
        """
        try:
            import ctypes
            from ctypes import wintypes

            SEE_MASK_INVOKEIDLIST = 12
            path = str(Path(file_path).absolute())

            # This opens the properties dialog
            subprocess.run(['explorer', '/select,', path])
            return True

        except Exception as e:
            print(f"Error showing properties: {e}")
            return False
