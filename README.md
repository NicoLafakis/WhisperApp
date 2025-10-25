# WhisperApp

A Windows 11 desktop application for push-to-talk transcription using OpenAI's Whisper API.

## Features

- **Push-to-Talk**: Hold `Ctrl+Shift+Space` to record, release to transcribe
- **Voice-Activated Navigation**: Control window positioning with voice commands (e.g., "Monitor one, quadrant one")
- **Customizable Hotkeys**: Configure your own keyboard shortcuts for push-to-talk and voice command toggle
- **Smart Text Insertion**: Automatically inserts transcribed text into the active text field
- **Multi-Monitor Support**: Move and organize windows across multiple monitors with voice commands
- **Quadrant Layout**: Organize windows into 4 quadrants per monitor for efficient screen management
- **Clipboard Fallback**: If no text field is active, copies to clipboard with notification
- **System Tray Integration**: Runs quietly in the background with easy access to features
- **Secure Settings**: Encrypted API key storage
- **Multi-language Support**: Supports multiple languages including English, Spanish, French, German, and more
- **Windows 11 Native**: Built specifically for Windows 11

## Screenshots

![System Tray](docs/tray.png)
![Settings Window](docs/settings.png)

## Installation

### Option 1: Download Pre-built Executable (Recommended)

1. Download `WhisperApp.exe` from the [Releases](../../releases) page
2. Run `WhisperApp.exe`
3. The app will appear in your system tray
4. Right-click the tray icon and select "Settings"
5. Enter your OpenAI API key

### Option 2: Build from Source

#### Prerequisites

- Windows 11
- Python 3.8 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

#### Build Steps

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/WhisperApp.git
   cd WhisperApp
   ```

2. Run the build script:
   ```bash
   build.bat
   ```

3. The executable will be created at `dist\WhisperApp.exe`

## Usage

### First Time Setup

1. Launch WhisperApp.exe
2. Right-click the system tray icon
3. Select "Settings"
4. Enter your OpenAI API key
5. (Optional) Adjust other settings like language preference and hotkeys
6. (Optional) Enable voice commands for window navigation
7. Click "Save"

### Push-to-Talk Transcription

1. Click on any text field (Word, Notepad, browser, etc.)
2. Press and hold `Ctrl+Shift+Space` (or your custom hotkey)
3. Speak while holding the keys
4. Release the keys when done speaking
5. The transcribed text will be automatically inserted at your cursor

### Voice-Activated Navigation

Enable voice commands from the system tray menu or settings:

1. Right-click the system tray icon
2. Click "Enable Voice Commands" (or use `Ctrl+Shift+V`)
3. Say a command like:
   - "Monitor one, quadrant one" - Move active window to monitor 1, top-left
   - "Monitor two, quadrant four" - Move active window to monitor 2, bottom-right
   - "Screen one, top right" - Move active window to monitor 1, top-right

#### Quadrant Layout

Each monitor is divided into 4 quadrants:

```
+-----+-----+
|  1  |  2  |  (Top)
+-----+-----+
|  3  |  4  |  (Bottom)
+-----+-----+
 Left Right
```

#### Supported Voice Commands

- "Monitor [1-9], quadrant [1-4]"
- "Screen [1-9], quadrant [1-4]"
- "Monitor [1-9], [top/bottom] [left/right]"

### If No Text Field is Active

If you're not in a text field:
- The transcription will be copied to your clipboard
- A notification will appear showing the transcribed text
- You can paste it anywhere with `Ctrl+V`

## Settings

The settings dialog is now organized into tabs for easy access:

### API Settings Tab

- **API Key**: Your OpenAI API key (required)
- **Model**: Whisper model to use (currently whisper-1)
- **Language**: Target language for transcription (or auto-detect)

### Hotkeys Tab

- **Push-to-Talk Hotkey**: Customize the keyboard shortcut for recording (default: `Ctrl+Shift+Space`)
- **Voice Command Toggle Hotkey**: Customize the shortcut to enable/disable voice commands (default: `Ctrl+Shift+V`)
- **Record Hotkey**: Click to easily capture a new key combination

### Voice Commands Tab

- **Enable Voice Navigation**: Toggle voice-activated window control
- **Show Notifications**: Display notifications when voice commands are executed
- **Sensitivity**: Adjust voice recognition sensitivity (Low, Medium, High)
- **Available Commands**: View list of supported voice commands

### Behavior Tab

- **Automatically copy to clipboard**: Always copy transcriptions to clipboard
- **Show transcription notifications**: Display notifications when transcription is complete

## Troubleshooting

### "API Key Required" Error

Make sure you've entered your OpenAI API key in Settings. You can get one from [OpenAI's website](https://platform.openai.com/api-keys).

### No Audio Recording

1. Check your microphone is connected and working
2. Make sure WhisperApp has microphone permissions in Windows Settings
3. Try restarting the application

### Text Not Inserting

1. Make sure you click in a text field before transcribing
2. Some applications may not support automatic text insertion
3. Check if the text was copied to clipboard as a fallback

### Application Won't Start

1. Make sure you have administrator privileges
2. Check Windows Defender isn't blocking the application
3. Try running as administrator

## System Requirements

- Windows 11
- Internet connection (for API calls)
- Microphone
- Minimum 4GB RAM recommended

## Privacy & Security

- API keys are encrypted and stored locally on your computer
- Audio recordings are temporary and deleted after transcription
- No data is collected or sent anywhere except to OpenAI's API for transcription

## Cost

WhisperApp is free and open source. However, you'll need an OpenAI API account:

- OpenAI's Whisper API pricing: $0.006 per minute of audio
- Example: 100 minutes of transcription = $0.60

## Development

### Project Structure

```
WhisperApp/
├── src/
│   ├── main.py                      # Main application
│   ├── config_manager.py            # Settings management
│   ├── audio_recorder.py            # Audio recording
│   ├── transcription_service.py     # OpenAI API integration
│   ├── text_inserter.py             # Text insertion logic
│   ├── settings_dialog.py           # Settings UI (tabbed)
│   ├── hotkey_manager.py            # Hotkey registration/management
│   ├── window_manager.py            # Window positioning and monitor detection
│   ├── command_parser.py            # Voice command parsing
│   ├── voice_command_listener.py    # Continuous voice listening
│   └── recording_indicator.py       # Visual recording feedback
├── assets/
│   ├── icon.png                     # App icon (PNG)
│   └── icon.ico                     # App icon (ICO)
├── requirements.txt                 # Python dependencies
├── whisperapp.spec                  # PyInstaller configuration
├── build.bat                        # Windows build script
└── README.md                        # This file
```

### Running in Development Mode

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Run the application
python src/main.py
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [PyQt5](https://www.riverbankcomputing.com/software/pyqt/)
- Powered by [OpenAI Whisper](https://openai.com/research/whisper)
- Icon created with Pillow

## Support

If you encounter any issues or have questions:

1. Check the [Troubleshooting](#troubleshooting) section
2. Open an issue on GitHub
3. Check existing issues for solutions

## Roadmap

- [x] Custom hotkey configuration
- [x] Voice commands for window navigation
- [x] Multi-monitor support
- [ ] Multiple language models
- [ ] Local Whisper model support (no API required)
- [ ] History of transcriptions
- [ ] Export transcriptions
- [ ] Custom wake word
- [ ] Additional voice commands (minimize, maximize, close windows)
- [ ] Voice command macros

## Version History

### v2.0.0 (2025-10-25)
- Added voice-activated navigation for window control
- Added customizable hotkeys for all functions
- Added multi-monitor support with quadrant layout
- Added tabbed settings interface
- Enhanced voice command system with continuous listening
- Improved hotkey management system
- Added voice command sensitivity settings

### v1.0.0 (2025-10-23)
- Initial release
- Push-to-talk transcription
- System tray integration
- Settings management
- Multi-language support
