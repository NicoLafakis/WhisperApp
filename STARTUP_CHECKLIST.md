# JARVIS WhisperApp - Startup Checklist

## Pre-Flight Check (Before Running)

### 1. System Requirements
- [x] **Windows 11** (or Windows 10)
- [x] **Python 3.8+** installed
- [x] **Microphone** connected and working
- [x] **Speakers/Headphones** for TTS output
- [x] **Internet connection** for OpenAI API

### 2. Dependencies Installation

Run this command to install all required packages:

```bash
pip install -r requirements.txt
```

**Key Dependencies:**
- `openai>=1.51.0` - OpenAI API (Whisper, GPT, TTS)
- `PyQt5==5.15.10` - GUI framework
- `pyaudio==0.2.14` - Microphone input
- `pygame>=2.5.0` - Audio playback
- `numpy>=1.24.0` - Audio processing
- `pywin32>=307` - Windows API
- `pycaw==20240210` - Audio control
- `psutil==5.9.8` - System info

### 3. API Configuration

**Get OpenAI API Key:**
1. Go to https://platform.openai.com/api-keys
2. Create a new API key
3. Copy the key

**Configure in WhisperApp:**
- Right-click tray icon → Settings → API Settings
- Paste your API key
- Click "Test API Key" to verify
- Click "Save"

**Or** set environment variable:
```bash
set WHISPER_API_KEY=your-api-key-here
```

### 4. First Run

```bash
python src/main.py
```

**Expected Behavior:**
- Tray icon appears in system tray
- If API key not configured: Welcome dialog appears
- Status shows "Ready"

## Testing JARVIS

### 1. Enable Voice Commands
- Right-click tray icon
- Check "Enable Voice Commands"
- Wait for "Listening for wake word..." notification

### 2. Test Wake Word
Say: **"Hey Jarvis"**

Expected: Notification "JARVIS: Yes?"

### 3. Test Simple Command
After wake word, say: **"What time is it?"**

Expected:
- JARVIS processes your question
- Speaks the current time
- Returns to wake word listening

### 4. Test Window Management
Say: **"Hey Jarvis"** then **"Move Chrome to the top of monitor 1"**

Expected:
- Chrome window moves to top half of monitor 1
- JARVIS confirms the action verbally

## Troubleshooting

### "API key not configured"
- Check Settings → API Settings
- Verify key starts with `sk-`
- Test the key with "Test API Key" button

### "Pygame init failed" or no audio output
**Windows 11 Fix:**
1. Check Windows Sound Settings
2. Ensure default playback device is set
3. Try running as Administrator
4. Check Windows Defender isn't blocking Python

**Fallback:** Uses Windows Media Player COM if pygame fails

### "PyAudio could not find input device"
1. Check microphone is plugged in
2. Windows Settings → Privacy → Microphone
3. Allow apps to access microphone
4. Restart WhisperApp

### "Whisper transcription failed"
- Check internet connection
- Verify API key has credits
- Check OpenAI status: https://status.openai.com

### "GPT function calling failed"
- Ensure using `gpt-4o-mini` or newer model
- Check API key has access to GPT-4o models
- Verify API credits are available

### No wake word detection
1. Check microphone volume (should be 80%+)
2. Speak clearly: "Hey Jarvis"
3. Adjust sensitivity: Settings → Voice Commands → Sensitivity
4. Check console output for transcription text

### TTS not speaking
1. Check system volume
2. Verify speakers/headphones connected
3. Check console for TTS errors
4. Try different TTS voice in settings

## Performance Optimization

### Reduce API Costs
- Set TTS model to `tts-1` (faster, cheaper) instead of `tts-1-hd`
- Set verbosity to "concise"
- Reduce context_length to 10

### Improve Response Speed
- Use `tts-1` instead of `tts-1-hd` (cuts 1-2 seconds)
- Reduce speaking_speed to 1.2 (faster playback)

### Better Transcription
- Use quiet environment
- Increase microphone volume
- Set sensitivity to "high"
- Speak clearly and not too fast

## Build for Distribution

### Using PyInstaller

```bash
pyinstaller whisperapp.spec
```

**Output:** `dist/WhisperApp.exe`

**First Run After Build:**
1. Double-click `WhisperApp.exe`
2. Configure API key (Settings)
3. Enable voice commands
4. Test with "Hey Jarvis"

### Common Build Issues

**"Module not found" errors:**
- Check `hiddenimports` in `whisperapp.spec`
- Ensure all JARVIS modules listed

**Audio not working in EXE:**
- Pygame DLLs might be missing
- Run with console enabled to see errors:
  - Change `console=False` to `console=True` in spec file

**Large EXE size:**
- Normal: 200-300 MB (includes Python, Qt, pygame, numpy)
- Use UPX compression (already enabled)

## Configuration Files

### Config Location
```
C:\Users\<YourUsername>\.whisperapp\config.json
```

### Default JARVIS Configuration
```json
{
  "jarvis": {
    "enabled": true,
    "model": "gpt-4o-mini",
    "voice": "onyx",
    "tts_model": "tts-1-hd",
    "speaking_speed": 1.0,
    "response_verbosity": "balanced",
    "wake_word": "jarvis"
  }
}
```

### Manual Configuration (Advanced)
Edit `config.json` directly to customize:
- Change wake word
- Adjust TTS voice (alloy, echo, fable, onyx, nova, shimmer)
- Change GPT model
- Modify verbosity level

## Logs and Debugging

### Enable Console Output
Run from command line:
```bash
python src/main.py
```

Watch for:
- `✓` marks = success
- Transcription output = "Whisper transcribed: <text>"
- Function calls = "Executing function: <name>"
- Errors = clear messages with suggestions

### Debug Mode
Add to config.json:
```json
{
  "debug": true
}
```

Provides:
- Verbose API call logs
- Function execution details
- Audio processing info

## Getting Help

### Check Documentation
- `JARVIS_IMPLEMENTATION.md` - Feature overview
- `README.md` - Original WhisperApp docs

### Common Issues
1. **API errors**: Check OpenAI dashboard for quota/limits
2. **Audio issues**: Restart with different audio device
3. **Slow responses**: Normal (2-7 seconds total)
4. **Wake word not detected**: Say louder, check transcription output

### Still Having Issues?
1. Run with console enabled
2. Copy error messages
3. Check OpenAI API status
4. Verify all dependencies installed
5. Try running as Administrator

---

**Ready to go? Say "Hey Jarvis" and start controlling your PC with your voice!** 🎤🤖
