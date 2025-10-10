# Whisper Speech-to-Text App

A push-to-talk speech-to-text application using OpenAI's Whisper model that converts your speech to text and types/pastes it anywhere on your computer.

## 📋 What You Need Before Starting

1. **Windows Computer** (Windows 10/11 recommended)
2. **Microphone** (built-in or external)
3. **Internet Connection** (for OpenAI API calls)
4. **OpenAI API Key** (see setup instructions below)

## 🗂️ Initial Setup (First Time Only)

### Step 1: Extract the Application
1. **Locate your downloaded file** (usually in Downloads folder)
2. **Right-click the ZIP file** → Select "Extract All..."
3. **Choose destination** (Desktop is recommended for easy access)
4. **Click "Extract"**
5. **Open the extracted folder** called `WhisperApp`

### Step 2: Install Python (If Not Already Installed)
1. **Check if Python is installed**:
   - Press `Windows + R`, type `cmd`, press Enter
   - Type `python --version` and press Enter
   - If you see a version number (like `Python 3.x.x`), Python is installed ✅
   - If you get an error, continue to install Python

2. **Install Python** (if needed):
   - Go to [python.org/downloads](https://python.org/downloads)
   - Click "Download Python" (latest version)
   - **Run the installer**
   - ⚠️ **IMPORTANT**: Check "Add Python to PATH" during installation
   - Click "Install Now"
   - Restart your computer after installation

### Step 3: Get OpenAI API Key
1. **Go to OpenAI website**:
   - Visit [platform.openai.com](https://platform.openai.com)
   - Sign up or log in to your account

2. **Create API Key**:
   - Click your profile → "View API Keys" (or "API Keys" in sidebar)
   - Click "Create new secret key"
   - **Copy the key immediately** (you won't see it again!)
   - Save it in a text file temporarily

3. **Add Credits** (Required):
   - Go to "Billing" in your OpenAI account
   - Add a payment method and credits ($5 minimum recommended)
   - The Whisper API is very affordable (~$0.006 per minute)

### Step 4: Install Application Dependencies
1. **Open PowerShell in the app folder**:
   - Navigate to your extracted `WhisperApp` folder
   - **Hold Shift + Right-click** in empty space → "Open PowerShell window here"
   - OR press `Windows + R`, type `powershell`, press Enter, then type:
     ```
     cd "C:\path\to\your\WhisperApp\folder"
     ```

2. **Install required packages**:
   ```
   pip install -r requirements.txt
   ```
   - Wait for installation to complete (may take 2-3 minutes)
   - Installs: audio processing, OpenAI API, system tray support, and more
   - You should see "Successfully installed..." messages

### Step 5: Set Up Your OpenAI API Key

**Option A: Environment Variable (Recommended)**
1. **Set the API key globally**:
   ```
   setx OPENAI_API_KEY "your-actual-api-key-here"
   ```
   - Replace `your-actual-api-key-here` with your real API key
   - **Important**: Include the quotes!

2. **Restart PowerShell/Terminal** for changes to take effect

**Option B: Enter in Settings UI**
- You can enter the API key directly in the app settings (less secure but easier)

## 🚀 Running the Application

### Method 1: Desktop Shortcut (Easiest)
1. **Create desktop shortcut**:
   - In your WhisperApp folder, right-click `create_shortcut.ps1`
   - Select "Run with PowerShell"
   - If prompted about execution policy, type `Y` and press Enter
   - Follow the on-screen prompts
   - A desktop shortcut will be created

2. **Start Whisper**:
   - **Double-click the "Whisper STT" shortcut** on your desktop
   - Settings window opens initially for configuration
   - **Close the settings window** - app continues running in system tray
   - **Look for the microphone icon** in your system tray (bottom-right corner)
   - The app runs silently in the background (no window appears)

### Method 2: Manual Launch
- **Silent mode**: Double-click `run_whisper_silent.bat`
- **Debug mode**: Double-click `run_whisper.bat` (shows terminal for troubleshooting)

### Method 3: Command Line
```
python whisper.py
```

## ⚙️ First-Time Configuration

When you run the app for the first time, a settings window will open:

### Required Settings:
1. **API Key Source**: 
   - Select "env" if you set environment variable
   - Select "inline" to enter key directly (then fill "API key" field)

2. **Model**: Leave as "whisper-1" (default)

3. **Test Your Setup**:
   - Click "Test Mic (3s)" button
   - **Speak clearly** during the 3-second recording
   - You should see a popup with your transcribed text
   - If it works, you're ready! Click "Save"

### Optional Settings:
- **Language**: Leave empty for auto-detect, or enter "en" for English only
- **Hotkey**: Default is "Ctrl+0" (you can change this)
- **Output Mode**: 
  - "paste" = faster, good for most apps
  - "type" = slower but works everywhere
- **Mic Gain**: Adjust if too quiet/loud (1.0 is normal)
- **Input Device**: Usually "None" (default microphone) works fine

## 🎯 How to Use Whisper

### System Tray Operation
- **Microphone icon** appears in system tray (bottom-right corner of screen)
- **Green icon** = Whisper is enabled and ready
- **Red icon** = Whisper is disabled
- **Right-click the icon** to access menu:
  - "Open Settings" - Configure the app
  - "Toggle Enable/Disable" - Turn Whisper on/off
  - "Exit" - Completely close the application

### Hotkeys (Global - Work Anywhere)
- **Ctrl+0**: Record speech (press once to start, again to stop and transcribe)
- **\\** (backslash): Toggle Whisper on/off

### Basic Usage Workflow
1. **Start the application** (using one of the methods above)
   - No window appears - it runs in the background
   - You'll see a settings window on first run only

2. **Position your cursor** where you want text to appear:
   - Click in any text field (email, document, chat, etc.)
   - The transcribed text will appear where your cursor is

3. **Record your speech**:
   - Press **Ctrl+0** to start recording
   - **Speak clearly** into your microphone
   - Press **Ctrl+0** again to stop and transcribe
   - Your speech will be converted to text and typed/pasted automatically

4. **Toggle on/off as needed**:
   - Press **\\** (backslash) to disable/enable Whisper
   - Useful when you want to temporarily turn off the hotkeys

### Detailed Step-by-Step Example
1. **Open any application** (Notepad, Word, email, chat app, etc.)
2. **Click where you want text** to make sure cursor is positioned
3. **Press and release Ctrl+0** - you'll see a console message "Recording started"
4. **Speak your message** clearly at normal speed
   - Example: "Hello, this is a test of the speech to text application"
5. **Press Ctrl+0 again** - recording stops and processing begins
6. **Wait 2-3 seconds** - text appears where your cursor was!
7. **Continue typing normally** or repeat the process for more speech-to-text

### Tips for Best Results
- **Speak clearly and at normal pace** (not too fast/slow)
- **Minimize background noise** when possible
- **Wait for processing** - don't press keys immediately after stopping recording
- **Use good microphone positioning** - 6-12 inches from mouth is ideal
- **Record 5-30 second chunks** for best accuracy and speed

### Working with Different Applications
- **Microsoft Word**: Works perfectly with paste mode
- **Email clients**: Gmail, Outlook, etc. work great
- **Chat applications**: Discord, Slack, Teams all supported
- **Code editors**: VS Code, Notepad++ work fine
- **Web browsers**: Type in any text field on any website
- **Note-taking apps**: OneNote, Notion, Obsidian all compatible

## 🔧 Advanced Settings

### Accessing Settings
- **If app is running**: Close it first (Ctrl+C in terminal or end process)
- **Run the app again**: Settings window appears automatically
- **Or**: Modify settings and click "Save" to restart hotkeys

### Complete Settings Reference

**API Key Settings:**
- **API key source**: 
  - `env` = Use environment variable (more secure)
  - `inline` = Enter key directly in app (convenient)
- **API key (inline)**: Only needed if source is "inline"

**Model Settings:**
- **Model**: Use "whisper-1" (OpenAI's official Whisper model)
- **Language**: 
  - Leave empty = Auto-detect language
  - "en" = Force English only
  - "es" = Force Spanish, etc.

**Hotkey Settings:**
- **Hotkey (toggle)**: Main recording key (default: Ctrl+0)
- **Capture button**: Click to record a new hotkey combination
- **Fixed toggle key**: \\ (backslash) - cannot be changed

**Audio Settings:**
- **Output mode**:
  - `paste` = Fast, uses clipboard (recommended)
  - `type` = Slower, types character by character
- **Mic gain**: 0.5-3.0 range
  - 1.0 = Normal volume
  - Higher = Amplify quiet microphones
  - Lower = Reduce loud microphones
- **Input device**: 
  - "None" = Default microphone
  - Select specific microphone if multiple available

### Performance Tuning
- **For quiet microphones**: Increase gain to 1.5-2.0
- **For noisy environments**: Keep gain at 1.0 or lower
- **For better accuracy**: Speak 6-12 inches from microphone
- **For faster processing**: Use shorter recordings (5-20 seconds)

## 🚨 Troubleshooting Guide

### Application Won't Start
**Problem**: Double-clicking does nothing or shows error
**Solutions**:
1. **Check Python installation**:
   ```
   python --version
   ```
   Should show Python 3.x.x

2. **Reinstall dependencies**:
   ```
   pip install -r requirements.txt
   ```

3. **Run in debug mode**: Use `run_whisper.bat` to see error messages

4. **Check system tray**: Look for microphone icon in bottom-right corner

### System Tray Issues
**Problem**: No tray icon appears or tray icon doesn't work
**Solutions**:
1. **Check tray dependencies**: Ensure pystray and Pillow installed
2. **Windows tray settings**: Settings → Personalization → Taskbar → "Select which icons appear on taskbar"
3. **Run as administrator**: Some systems require elevated permissions for tray icons
4. **Restart Windows Explorer**: Ctrl+Shift+Esc → Find "Windows Explorer" → Restart

### API Key Issues
**Problem**: "Missing API key" or "Authentication failed"
**Solutions**:
1. **Verify your API key** at [platform.openai.com](https://platform.openai.com)
2. **Check billing**: Ensure you have credits in your OpenAI account
3. **Re-set environment variable**:
   ```
   setx OPENAI_API_KEY "your-key-here"
   ```
   Then restart PowerShell/Terminal

4. **Try inline mode**: Set API key directly in settings

### Recording Issues
**Problem**: "Test Mic" fails or no audio recorded
**Solutions**:
1. **Check microphone permissions**:
   - Windows Settings → Privacy → Microphone
   - Allow desktop apps to access microphone

2. **Test microphone**: Use Windows Voice Recorder app first

3. **Try different input device** in settings

4. **Adjust microphone gain** (try 1.5-2.0)

5. **Check for audio conflicts**: Close other audio applications

### Transcription Issues
**Problem**: Wrong words or no text output
**Solutions**:
1. **Speak more clearly**: Slower, clearer pronunciation
2. **Reduce background noise**: Close windows, turn off fans
3. **Check recording length**: 3-30 seconds works best
4. **Try setting language**: Add "en" in language field for English
5. **Test internet connection**: API requires internet access

### Hotkey Issues
**Problem**: Ctrl+0 or \\ don't work
**Solutions**:
1. **Check if app is running**: Look for Python process in Task Manager
2. **Try different hotkey**: Change in settings (avoid conflicts)
3. **Run as administrator**: Right-click batch file → "Run as administrator"
4. **Check for conflicting software**: Other hotkey programs may interfere
5. **Toggle on/off**: Press \\ to enable if disabled

### Text Output Issues
**Problem**: Text appears in wrong place or doesn't appear
**Solutions**:
1. **Click where you want text**: Ensure cursor is positioned first
2. **Try different output mode**: Switch between "paste" and "type" in settings
3. **Check clipboard permissions**: Some apps block paste operations
4. **Wait for processing**: Don't click immediately after recording
5. **Try in Notepad first**: Test basic functionality

### Performance Issues
**Problem**: Slow transcription or high CPU usage
**Solutions**:
1. **Keep recordings short**: 5-20 seconds optimal
2. **Close unnecessary programs**: Free up system resources
3. **Check internet speed**: Slow connection affects API calls
4. **Lower microphone gain**: Reduces processing load

### Emergency Reset
**If everything is broken**:
1. **Delete config file**: Remove `config.json` from `%APPDATA%\Whisper\`
2. **Reinstall dependencies**: 
   ```
   pip uninstall -r requirements.txt
   pip install -r requirements.txt
   ```
3. **Restart computer**: Clears all processes and permissions
4. **Re-run setup**: Follow installation steps again

## 📁 File Reference

### Core Files (Don't Delete!)
- **`whisper.py`** - Main application code with system tray support
- **`requirements.txt`** - List of Python packages needed (includes tray dependencies)

### Launcher Files
- **`run_whisper_silent.bat`** - Launch app without showing terminal window (recommended)
- **`run_whisper.bat`** - Launch app with terminal visible (for debugging)
- **`create_shortcut.ps1`** - PowerShell script to create desktop shortcut

### Documentation
- **`README.md`** - This complete guide you're reading

### Generated Files (Created Automatically)
- **Desktop shortcut** - "Whisper STT.lnk" created on your desktop
- **Config file** - Stored in `%APPDATA%\Whisper\config.json` (settings)

## 💡 Tips & Best Practices

### For Best Accuracy
- **Speak naturally** - don't over-enunciate or speak robotically
- **Use a good microphone** - built-in laptop mics work, but external is better
- **Record in quiet environment** - background noise reduces accuracy
- **Keep recordings moderate length** - 5-30 seconds is optimal
- **Speak consistently** - same distance from microphone

### For Productivity
- **Learn the hotkeys** - Ctrl+0 becomes second nature quickly
- **Use the toggle** - Press \\ to disable when not needed
- **Position cursor first** - always click where you want text before recording
- **Practice the workflow** - start, speak, stop becomes very fast
- **Use in chunks** - record sentences or paragraphs, not entire documents

### For Reliability  
- **Keep app running** - leave it in background, don't close frequently
- **Monitor API usage** - check your OpenAI billing periodically
- **Backup settings** - note your preferred configuration
- **Test after updates** - Windows updates can affect microphone permissions
- **Have backup method** - keep keyboard/typing as fallback

## 🔒 Security & Privacy Notes

- **API Key Security**: Environment variables are more secure than inline storage
- **Data Privacy**: Your voice is sent to OpenAI for processing (see their privacy policy)
- **Local Storage**: Only settings are stored locally, no audio recordings saved
- **Network Usage**: Requires internet for each transcription request
- **Permissions**: App needs microphone access to record audio

## 📊 Cost Information

- **Whisper API Cost**: ~$0.006 per minute of audio
- **Example**: 1 hour of total recording = ~$0.36
- **Monthly Usage**: Heavy users might spend $5-20/month
- **Free Tier**: OpenAI often provides initial credits for new accounts
- **Billing**: Check usage at [platform.openai.com](https://platform.openai.com) → Billing

## 🆘 Getting Additional Help

### If This Guide Doesn't Solve Your Problem:
1. **Run in debug mode**: Use `run_whisper.bat` to see detailed error messages
2. **Check OpenAI status**: Visit [status.openai.com](https://status.openai.com) for service issues
3. **Verify system requirements**: Windows 10/11, Python 3.8+, active internet
4. **Test with minimal setup**: Try with default settings first
5. **Check Windows permissions**: Microphone, network, and app permissions

### Common Environment Issues:
- **Corporate networks**: May block OpenAI API calls
- **Antivirus software**: May interfere with hotkey registration
- **Multiple Python installations**: Can cause package conflicts
- **Windows updates**: May reset microphone permissions
- **Conflicting software**: Other voice/hotkey apps may interfere

---

## 🎉 You're All Set!

After following this guide, you should have:
✅ Whisper installed and configured  
✅ Desktop shortcut for easy launching  
✅ API key properly set up  
✅ Microphone tested and working  
✅ Understanding of hotkeys and workflow  

**Ready to use**: Press Ctrl+0, speak, press Ctrl+0 again, and watch your speech become text instantly!