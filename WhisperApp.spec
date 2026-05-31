# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for WhisperApp
# Run: pyinstaller WhisperApp.spec

from PyInstaller.building.build_main import Analysis, PYZ, EXE
from PyInstaller.building.api import COLLECT
from pathlib import Path
import sys

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))

import whisperapp

APP_NAME = "WhisperApp"
APP_VERSION = whisperapp.__version__

a = Analysis(
    ['whisperapp\\__main__.py'],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[],
    hiddenimports=[
        'keyboard._winkeyboard',
        'pyaudio._portaudio',
        'cryptography.hazmat.bindings._rust',
        'certifi',
        'openai._base_client',
        'openai._client',
        'openai.resources.audio.transcriptions',
        'httpx',
        'jiter',
        'pydantic',
        'pydantic_core',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'IPython',
        'PIL',
        'matplotlib',
        'numba',
        'numpy',
        'pandas',
        'pygame',
        'pytest',
        'scipy',
        'sympy',
        'torch',
        'torchgen',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version='version_info.txt',
)
