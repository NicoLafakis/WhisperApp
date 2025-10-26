"""
PyInstaller hook for speech_recognition package
Ensures all audio-related stdlib modules are included
"""
from PyInstaller.utils.hooks import collect_all

# Collect all speech_recognition data and submodules
datas, binaries, hiddenimports = collect_all('speech_recognition')

# Add deprecated audio modules that speech_recognition depends on
# These are needed for Python 3.11 (deprecated but not yet removed)
hiddenimports += [
    'aifc',      # Audio Interchange File Format support
    'audioop',   # Audio operations
    'wave',      # WAV file support
    'sndhdr',    # Sound file header identification
    'chunk',     # Chunk file support
    'sunau',     # Sun AU file support
]
