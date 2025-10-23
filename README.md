# WhisperApp

A Windows 11 desktop application for push-to-talk transcription using OpenAI's Whisper API.

## Features

- **Push-to-Talk**: Hold `Ctrl+Shift+Space` to record, release to transcribe
- **Smart Text Insertion**: Automatically inserts transcribed text into the active text field
- **Clipboard Fallback**: If no text field is active, copies to clipboard with notification
- **System Tray Integration**: Runs quietly in the background
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
5. (Optional) Adjust other settings like language preference
6. Click "Save"

### Using the App

1. Click on any text field (Word, Notepad, browser, etc.)
2. Press and hold `Ctrl+Shift+Space`
3. Speak while holding the keys
4. Release the keys when done speaking
5. The transcribed text will be automatically inserted at your cursor

### If No Text Field is Active

If you're not in a text field:
- The transcription will be copied to your clipboard
- A notification will appear showing the transcribed text
- You can paste it anywhere with `Ctrl+V`

## Settings

### API Configuration

- **API Key**: Your OpenAI API key (required)
- **Model**: Whisper model to use (currently whisper-1)
- **Language**: Target language for transcription (or auto-detect)

### Behavior

- **Automatically copy to clipboard**: Always copy transcriptions to clipboard
- **Show notifications**: Display notifications when transcription is complete

### Hotkey

- Default: `Ctrl+Shift+Space`
- Customization coming in future updates

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
│   ├── main.py                 # Main application
│   ├── config_manager.py       # Settings management
│   ├── audio_recorder.py       # Audio recording
│   ├── transcription_service.py # OpenAI API integration
│   ├── text_inserter.py        # Text insertion logic
│   └── settings_dialog.py      # Settings UI
├── assets/
│   ├── icon.png                # App icon (PNG)
│   └── icon.ico                # App icon (ICO)
├── requirements.txt            # Python dependencies
├── whisperapp.spec            # PyInstaller configuration
├── build.bat                   # Windows build script
└── README.md                   # This file
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

- [ ] Custom hotkey configuration
- [ ] Multiple language models
- [ ] Local Whisper model support (no API required)
- [ ] History of transcriptions
- [ ] Export transcriptions
- [ ] Voice commands
- [ ] Custom wake word

## Version History

### v1.0.0 (2025-10-23)
- Initial release
- Push-to-talk transcription
- System tray integration
- Settings management
- Multi-language support
