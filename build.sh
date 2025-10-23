#!/bin/bash
# Build script for WhisperApp

echo "================================"
echo "WhisperApp Build Script"
echo "================================"
echo ""

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 is not installed"
    echo "Please install Python 3.8+ from https://www.python.org/"
    exit 1
fi

echo "Step 1: Creating virtual environment..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

echo "Step 2: Activating virtual environment..."
source venv/bin/activate

echo "Step 3: Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt
pip install Pillow

echo "Step 4: Creating application icon..."
python create_icon.py

echo "Step 5: Building executable with PyInstaller..."
pyinstaller whisperapp.spec --clean

echo ""
echo "================================"
echo "Build complete!"
echo "================================"
echo ""
echo "The executable is located at: dist/WhisperApp"
echo ""
