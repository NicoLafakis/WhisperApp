# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Collect data and binaries
datas = []
binaries = []
hiddenimports = []

# Collect pygame for audio playback
try:
    tmp_ret = collect_all('pygame')
    datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
except:
    print("Warning: pygame not found, TTS audio playback may not work")

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas + [
        ('assets/icon.png', 'assets'),
        ('assets/icon.ico', 'assets'),
    ],
    hiddenimports=hiddenimports + [
        # PyQt5
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'PyQt5.sip',
        # OpenAI
        'openai',
        'openai.types',
        'openai.types.audio',
        'openai.types.chat',
        # Audio
        'pyaudio',
        'pygame',
        'pygame.mixer',
        # Keyboard/Mouse
        'keyboard',
        'pyperclip',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        # Notifications
        'plyer',
        # Encryption
        'cryptography',
        'cryptography.fernet',
        # Audio modules for legacy compatibility
        'wave',
        # Numeric processing
        'numpy',
        'numpy.core',
        'numpy.core._multiarray_umath',
        # System modules
        'comtypes',
        'pycaw',
        'psutil',
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        # JARVIS modules
        'whisper_voice_listener',
        'natural_language_processor',
        'function_registry',
        'text_to_speech',
        'conversation_manager',
    ],
    hookspath=['hooks'],
    hooksconfig={},
    runtime_hooks=['hooks/runtime-hook-aifc.py'],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WhisperApp',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',
)
