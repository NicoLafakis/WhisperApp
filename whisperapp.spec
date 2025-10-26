# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None

# Collect all speech_recognition submodules and data
datas = []
binaries = []
hiddenimports = []

# Collect speech_recognition package completely
tmp_ret = collect_all('speech_recognition')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

a = Analysis(
    ['src/main.py'],
    pathex=['src'],
    binaries=binaries,
    datas=datas + [
        ('assets/icon.png', 'assets'),
        ('assets/icon.ico', 'assets'),
    ],
    hiddenimports=hiddenimports + [
        'PyQt5',
        'PyQt5.QtCore',
        'PyQt5.QtGui',
        'PyQt5.QtWidgets',
        'openai',
        'pyaudio',
        'keyboard',
        'pyperclip',
        'pynput',
        'pynput.keyboard',
        'pynput.mouse',
        'plyer',
        'cryptography',
        'speech_recognition',
        # Audio modules (deprecated but still needed in Python 3.11)
        'aifc',
        'audioop',
        'wave',
        'sndhdr',
        'chunk',
        'sunau',
        # PyQt5 submodules
        'PyQt5.sip',
        # System modules
        'comtypes',
        'pycaw',
        'psutil',
        'vosk',
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
