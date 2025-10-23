# WhisperApp Quick Start Guide

Get up and running with WhisperApp in 5 minutes!

## For Users (Running the App)

### Step 1: Get Your OpenAI API Key

1. Go to https://platform.openai.com/api-keys
2. Sign up or log in
3. Click "Create new secret key"
4. Copy the key (starts with `sk-...`)
5. Keep it safe - you'll need it in Step 3

### Step 2: Download and Run

**Option A: Pre-built Executable**
1. Download `WhisperApp.exe` from the releases page
2. Double-click to run
3. Look for the microphone icon in your system tray (bottom-right corner)

**Option B: Build from Source**
1. Open Command Prompt in the WhisperApp folder
2. Run: `build.bat`
3. Wait for it to finish
4. Run: `dist\WhisperApp.exe`

### Step 3: Configure Your API Key

1. Right-click the microphone icon in the system tray
2. Click "Settings"
3. Paste your API key in the "API Key" field
4. Click "Test API Key" to verify it works
5. Click "Save"

### Step 4: Start Transcribing!

1. Click anywhere you can type (Notepad, Word, browser, etc.)
2. Press and hold `Ctrl + Shift + Space`
3. Speak: "Hello, this is a test transcription"
4. Release the keys
5. Watch the text appear where your cursor is!

## Tips & Tricks

### Where Can I Use It?

WhisperApp works in:
- Microsoft Word
- Notepad
- Web browsers (Gmail, Google Docs, etc.)
- Slack, Discord, Teams
- Any text editor
- Most applications with text input

### What If I'm Not in a Text Field?

If you transcribe without an active text field:
- Text is copied to your clipboard
- A notification shows the transcribed text
- Paste anywhere with `Ctrl + V`

### Best Practices for Accuracy

1. **Speak clearly** - Enunciate your words
2. **Reduce background noise** - Find a quiet space
3. **Use a good microphone** - Built-in laptop mics work, but external mics are better
4. **Speak in complete sentences** - Whisper works better with context
5. **Pause between sentences** - Helps with punctuation

### Supported Languages

WhisperApp supports 50+ languages including:
- English
- Spanish
- French
- German
- Italian
- Portuguese
- Russian
- Japanese
- Korean
- Chinese
- And many more!

To change language:
1. Right-click system tray icon
2. Click "Settings"
3. Select your language from dropdown
4. Click "Save"

## Troubleshooting

### "API Key Required" Error

**Solution**: You need to configure your API key
1. Right-click system tray icon
2. Click "Settings"
3. Enter your API key
4. Click "Save"

### No Sound Being Recorded

**Solution**: Check microphone permissions
1. Windows Settings → Privacy → Microphone
2. Make sure microphone access is enabled
3. Restart WhisperApp

### Text Not Appearing

**Solution**: Make sure you click in a text field first
- Click in Notepad, Word, or browser
- Make sure the cursor is blinking
- Try the hotkey again

### App Not Starting

**Solution**: Run as administrator
1. Right-click `WhisperApp.exe`
2. Select "Run as administrator"
3. Allow it in Windows Defender if prompted

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl + Shift + Space` | Push-to-talk (hold to record) |
| Right-click tray icon | Open menu |

## Cost Information

WhisperApp is free, but you pay for OpenAI API usage:

- **Price**: $0.006 per minute of audio
- **Example**: 100 minutes = $0.60
- **Average**: Most people spend less than $5/month

Check your usage at: https://platform.openai.com/usage

## Privacy

- Your API key is encrypted and stored locally
- Audio is sent only to OpenAI for transcription
- No data is stored or collected by WhisperApp
- Temporary audio files are deleted immediately after transcription

## Getting Help

1. Check the [README.md](README.md) for detailed documentation
2. Check the [Troubleshooting](#troubleshooting) section above
3. Open an issue on GitHub

## What's Next?

Now that you're set up:

1. **Practice**: Try transcribing different types of content
2. **Explore Settings**: Customize language and behavior
3. **Share Feedback**: Let us know how we can improve!

## Pro Tips

### Email Writing
1. Open Gmail
2. Click "Compose"
3. Use WhisperApp to dictate your email
4. Edit as needed
5. Send!

### Document Creation
1. Open Word or Google Docs
2. Start with an outline
3. Use WhisperApp to fill in each section
4. Much faster than typing!

### Meeting Notes
1. During a meeting, open Notepad
2. Use WhisperApp to capture key points
3. No need to type - just speak
4. Clean up notes after the meeting

### Coding Documentation
1. Open your IDE
2. Navigate to where you need comments
3. Use WhisperApp to dictate code explanations
4. Perfect for adding docstrings!

---

**Enjoy using WhisperApp! Happy transcribing!** 🎤
