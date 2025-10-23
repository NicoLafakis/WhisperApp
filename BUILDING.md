# Building WhisperApp from Source

This guide will walk you through building WhisperApp into a standalone Windows executable.

## Prerequisites

### Required Software

1. **Python 3.8 or higher**
   - Download from: https://www.python.org/downloads/
   - During installation, make sure to check "Add Python to PATH"

2. **Git** (optional, for cloning)
   - Download from: https://git-scm.com/downloads

3. **OpenAI API Key**
   - Sign up at: https://platform.openai.com/
   - Create an API key at: https://platform.openai.com/api-keys

## Step-by-Step Build Instructions

### Method 1: Using the Build Script (Easiest)

1. **Open Command Prompt or PowerShell**
   - Press `Win + R`
   - Type `cmd` and press Enter

2. **Navigate to the project directory**
   ```bash
   cd path\to\WhisperApp
   ```

3. **Run the build script**
   ```bash
   build.bat
   ```

4. **Wait for the build to complete**
   - The script will create a virtual environment
   - Install all dependencies
   - Generate the application icon
   - Build the executable

5. **Find your executable**
   - Location: `dist\WhisperApp.exe`
   - You can copy this file anywhere you want

### Method 2: Manual Build

If the automatic build script doesn't work, follow these steps:

1. **Create a virtual environment**
   ```bash
   python -m venv venv
   ```

2. **Activate the virtual environment**
   ```bash
   venv\Scripts\activate
   ```

3. **Upgrade pip**
   ```bash
   python -m pip install --upgrade pip
   ```

4. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   pip install Pillow
   ```

5. **Create the application icon**
   ```bash
   python create_icon.py
   ```

6. **Build with PyInstaller**
   ```bash
   pyinstaller whisperapp.spec --clean
   ```

7. **Find your executable**
   - Location: `dist\WhisperApp.exe`

## Troubleshooting Build Issues

### "Python is not recognized"

**Problem**: Python is not in your system PATH

**Solution**:
1. Reinstall Python and check "Add Python to PATH"
2. Or manually add Python to PATH:
   - Search for "Environment Variables" in Windows
   - Edit the "Path" variable
   - Add your Python installation directory

### "pip is not recognized"

**Problem**: pip is not installed or not in PATH

**Solution**:
```bash
python -m ensurepip --upgrade
python -m pip install --upgrade pip
```

### PyAudio Installation Fails

**Problem**: PyAudio requires additional build tools on Windows

**Solution**:
1. Download the pre-built wheel from: https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
2. Install it manually:
   ```bash
   pip install PyAudio-0.2.14-cp311-cp311-win_amd64.whl
   ```
   (Adjust filename based on your Python version)

### "UPX is not available"

**Problem**: PyInstaller can't find UPX for compression

**Solution**: This is just a warning, not an error. The build will still work.
- To fix: Download UPX from https://upx.github.io/ and add to PATH
- Or modify `whisperapp.spec` and set `upx=False`

### Build succeeds but .exe doesn't run

**Problem**: Missing dependencies or antivirus blocking

**Solution**:
1. Check Windows Defender/Antivirus isn't blocking the exe
2. Try running from command line to see error messages:
   ```bash
   dist\WhisperApp.exe
   ```
3. Make sure all files in `dist\` folder are present

### "Failed to execute script"

**Problem**: Python dependencies missing or corrupted

**Solution**:
1. Clean build and try again:
   ```bash
   rmdir /s /q build dist
   pyinstaller whisperapp.spec --clean
   ```

2. Make sure virtual environment is activated
3. Reinstall all dependencies

## Build Configuration

### Customizing the Build

Edit `whisperapp.spec` to customize the build:

```python
# Change the executable name
name='WhisperApp',

# Include additional data files
datas=[
    ('assets/icon.png', 'assets'),
    ('your_file.txt', '.'),
],

# Hide/show console window
console=False,  # False = no console, True = show console

# Change icon
icon='assets/icon.ico',
```

### Creating a Smaller Executable

To reduce file size:

1. Remove unused imports from source files
2. Use `--exclude-module` in PyInstaller:
   ```bash
   pyinstaller whisperapp.spec --exclude-module matplotlib --exclude-module numpy
   ```

3. Disable UPX compression (sometimes makes it larger):
   - In `whisperapp.spec`, set `upx=False`

## Distribution

### Creating an Installer

You can create a professional installer using:

1. **Inno Setup** (Free)
   - Download: https://jrsoftware.org/isinfo.php
   - Create installer script for WhisperApp

2. **NSIS** (Free)
   - Download: https://nsis.sourceforge.io/
   - More complex but very powerful

3. **Advanced Installer** (Commercial)
   - Download: https://www.advancedinstaller.com/

### Simple Distribution

For simple distribution:

1. Create a ZIP file containing:
   - `WhisperApp.exe`
   - README.txt (basic instructions)
   - LICENSE.txt

2. Users can extract and run WhisperApp.exe directly

## Testing Your Build

Before distributing, test the executable:

1. **Test on a clean Windows 11 VM or PC**
   - This ensures all dependencies are bundled

2. **Test basic functionality**:
   - Application starts
   - System tray icon appears
   - Settings dialog opens
   - Can save API key
   - Recording works
   - Transcription works

3. **Test error conditions**:
   - Invalid API key
   - No internet connection
   - No microphone

## Build Optimization

### Faster Builds

For development:
```bash
# Use onefile mode (slower startup, easier distribution)
pyinstaller --onefile src/main.py

# Use onedir mode (faster startup, multiple files)
pyinstaller --onedir src/main.py
```

### Debug Build

To see console output for debugging:
1. Edit `whisperapp.spec`
2. Set `console=True`
3. Rebuild

## Continuous Integration

For automated builds, you can use GitHub Actions:

```yaml
name: Build WhisperApp

on: [push]

jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: python create_icon.py
      - run: pyinstaller whisperapp.spec
      - uses: actions/upload-artifact@v2
        with:
          name: WhisperApp
          path: dist/WhisperApp.exe
```

## Support

If you encounter build issues:

1. Check this troubleshooting guide
2. Search GitHub issues
3. Create a new issue with:
   - Your Python version (`python --version`)
   - Your OS version
   - Full error message
   - Build log

## Additional Resources

- [PyInstaller Documentation](https://pyinstaller.org/en/stable/)
- [PyQt5 Documentation](https://www.riverbankcomputing.com/static/Docs/PyQt5/)
- [Python Packaging Guide](https://packaging.python.org/)
