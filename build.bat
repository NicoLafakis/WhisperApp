@echo off
REM Build script for WhisperApp on Windows

echo ================================
echo WhisperApp Build Script
echo ================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo Step 1: Creating virtual environment...
if not exist venv (
    python -m venv venv
)

echo Step 2: Activating virtual environment...
call venv\Scripts\activate.bat

echo Step 3: Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt
pip install Pillow

echo Step 4: Creating application icon...
python create_icon.py

echo Step 5: Building executable with PyInstaller...
pyinstaller whisperapp.spec --clean

echo.
echo ================================
echo Build complete!
echo ================================
echo.
echo The executable is located at: dist\WhisperApp.exe
echo.
echo You can now:
echo 1. Run dist\WhisperApp.exe to start the application
echo 2. Copy dist\WhisperApp.exe to any location
echo 3. Create a shortcut on your desktop
echo.
pause
