# JARVIS Setup Guide

Complete step-by-step guide to get JARVIS up and running.

## Prerequisites Checklist

Before you begin, ensure you have:

- [ ] Windows 11 (or Windows 10)
- [ ] Node.js 18+ installed
- [ ] npm or yarn package manager
- [ ] Git (for cloning the repository)
- [ ] OpenAI API account with credits
- [ ] ElevenLabs API account (free tier works)
- [ ] Microphone and speakers
- [ ] ~500MB free disk space

## Step 1: Install Node.js

1. Download Node.js from https://nodejs.org/
2. Choose LTS version (18.x or higher)
3. Run the installer
4. Verify installation:

```bash
node --version  # Should show v18.x.x or higher
npm --version   # Should show 9.x.x or higher
```

## Step 2: Get API Keys

### OpenAI API Key

1. Go to https://platform.openai.com/
2. Sign up or log in
3. Navigate to API Keys section
4. Click "Create new secret key"
5. **Important**: Copy the key immediately (you won't see it again)
6. Add credits to your account (minimum $5 recommended)

**Required Model Access:**
- `gpt-4o-realtime-preview-2024-10-01` (check your account has access)
- `whisper-1` (generally available)
- `gpt-4o-mini` (generally available)

### ElevenLabs API Key

1. Go to https://elevenlabs.io/
2. Sign up (free tier available)
3. Navigate to Profile → API Keys
4. Copy your API key
5. Choose a voice ID:
   - Browse voices at https://elevenlabs.io/voice-library
   - Default: `EXAVITQu4MsJ5X4xQvF9` (Rachel voice)
   - Or use your own voice ID

## Step 3: Clone and Install

1. **Clone the repository**

```bash
git clone https://github.com/NicoLafakis/WhisperApp.git
cd WhisperApp
```

2. **Install dependencies**

```bash
npm install
```

This will install:
- Electron (application framework)
- React (UI framework)
- OpenAI SDK (API client)
- ElevenLabs SDK (voice synthesis)
- Audio processing libraries
- And more...

**Expected time**: 2-5 minutes depending on internet speed

## Step 4: Configure Environment

1. **Copy the example environment file**

```bash
copy .env.example .env
```

On Mac/Linux:
```bash
cp .env.example .env
```

2. **Edit `.env` file**

Open `.env` in your favorite text editor and fill in:

```env
# ===== REQUIRED =====
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ELEVENLABS_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
ELEVENLABS_VOICE_ID=EXAVITQu4MsJ5X4xQvF9

# ===== OPTIONAL (defaults provided) =====

# Cost Management
DAILY_BUDGET_USD=1.00        # Max cost per day
MONTHLY_BUDGET_USD=30.00     # Max cost per month

# Wake Word
WAKE_WORD=jarvis             # What word activates JARVIS
WAKE_WORD_SENSITIVITY=0.5    # 0.0-1.0 (higher = more sensitive)

# Mode Settings
DEFAULT_MODE=premium         # or "efficient"
PEAK_HOURS_START=9           # 9 AM
PEAK_HOURS_END=17            # 5 PM (uses premium during these hours)

# Audio Settings (don't change unless you know what you're doing)
SAMPLE_RATE=16000
AUDIO_CHANNELS=1
```

**Important**: Make sure there are no spaces around the `=` sign!

## Step 5: Build the Application

1. **Build the renderer (React UI)**

```bash
npm run build:renderer
```

2. **Build the main process (Electron backend)**

```bash
npm run build:main
```

Or build both at once:

```bash
npm run build
```

**Expected time**: 30-60 seconds

## Step 6: First Run (Development Mode)

For your first run, use development mode to see detailed logs:

```bash
npm run dev
```

This will:
1. Start the Vite dev server (React UI)
2. Compile TypeScript (Electron backend)
3. Launch the Electron app
4. Open developer tools

**What to expect:**
- JARVIS window appears
- System tray icon appears (bottom-right, near clock)
- Console shows initialization logs
- UI shows "Idle" status

## Step 7: Test Your Setup

### Test 1: Check Audio Input

1. Check system tray icon
2. Right-click → "Start Listening"
3. Check if status changes to "Listening"

If this fails:
- Check microphone permissions in Windows Settings
- Verify microphone is set as default device
- Check console for error messages

### Test 2: Manual Wake Word Trigger

1. Click the JARVIS window to show it
2. Click "Trigger Wake Word" button
3. Speak a simple command: "What time is it?"
4. Wait for response

If this works, you're ready to go!

### Test 3: Actual Wake Word

1. Ensure JARVIS is in "Idle" status
2. Say "Jarvis" clearly
3. Wait for status to change to "Listening"
4. Say a command

If wake word doesn't work:
- Adjust `WAKE_WORD_SENSITIVITY` in `.env`
- Speak more clearly/loudly
- Check microphone input level in Windows

## Step 8: Production Build (Optional)

For daily use, build a standalone executable:

```bash
npm run package
```

This creates an installer in the `release` folder:
- `JARVIS-Setup.exe` (Windows installer)

Run the installer and JARVIS will:
- Install to Program Files
- Add to startup (optional)
- Create desktop shortcut
- Add to Windows Search

## Common Issues & Solutions

### Issue: "Module not found" errors

**Solution**:
```bash
rm -rf node_modules package-lock.json
npm install
```

### Issue: OpenAI API errors

**Possible causes**:
1. Invalid API key → Check `.env` for typos
2. No credits → Add funds to your OpenAI account
3. No model access → Request access to Realtime API

**Check your setup**:
```bash
# Test API key
curl https://api.openai.com/v1/models \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### Issue: ElevenLabs errors

**Possible causes**:
1. Invalid API key
2. Exceeded free tier quota
3. Invalid voice ID

**Test ElevenLabs**:
Go to https://elevenlabs.io/app/speech-synthesis and try generating speech

### Issue: No audio output

**Solutions**:
1. Check speaker volume
2. Verify default audio output device
3. Check Windows audio permissions
4. Try different audio device

### Issue: High CPU usage

**Causes**:
- Audio capture runs continuously (expected)
- Multiple instances running

**Solution**:
- This is normal for always-listening mode
- Check Task Manager for multiple Electron processes

### Issue: High costs

**Solutions**:
1. Lower daily budget in `.env`
2. Set `DEFAULT_MODE=efficient`
3. Adjust peak hours to limit premium usage
4. Review cost dashboard in UI

## Audio Setup Tips

### Microphone Selection

**Best**: Desktop USB microphone (Blue Yeti, etc.)
**Good**: Laptop built-in mic
**Okay**: Headset mic
**Poor**: Cheap USB mics with background noise

### Microphone Settings (Windows 11)

1. Open Settings → System → Sound
2. Input → Choose your microphone
3. Click on microphone → Properties
4. Set levels:
   - Volume: 80-100%
   - Boost: 0-10dB (start low)
5. Enhancements:
   - ✅ Noise suppression
   - ✅ Echo cancellation
   - ❌ Disable all others

### Environment

**Good**:
- Quiet room
- Minimal echo
- Close to microphone (1-2 feet)

**Bad**:
- Noisy environment
- Far from microphone
- Lots of echo

## Performance Tuning

### For Faster Response

1. Set `DEFAULT_MODE=premium`
2. Keep connection alive (don't stop/start)
3. Minimize other network usage

### For Lower Cost

1. Set `DEFAULT_MODE=efficient`
2. Set lower budgets
3. Limit peak hours

### For Better Accuracy

1. Speak clearly and at normal pace
2. Reduce background noise
3. Use better microphone
4. Adjust wake word sensitivity

## Next Steps

Now that JARVIS is running:

1. **Read the README** for usage examples
2. **Check ARCHITECTURE.md** to understand how it works
3. **Experiment with commands** (see README for examples)
4. **Monitor costs** in the UI dashboard
5. **Customize settings** in `.env` as needed

## Getting Help

If you're stuck:

1. Check the [Troubleshooting](#common-issues--solutions) section above
2. Review logs in `logs/jarvis-YYYY-MM-DD.log`
3. Open an issue on GitHub with:
   - Your OS version
   - Node.js version
   - Error messages
   - Steps to reproduce

## Security Notes

**Protecting Your API Keys**:

1. ⚠️ Never commit `.env` to git (it's in `.gitignore`)
2. ⚠️ Don't share your `.env` file
3. ⚠️ If keys are exposed, regenerate them immediately
4. ✅ Use environment variables in production
5. ✅ Consider Windows Credential Manager for storage

**Function Security**:

- JARVIS can control your computer
- Review functions before allowing confirmation-required actions
- Blocked functions can't be executed under any circumstance
- Check `src/shared/utils/config.ts` for security settings

## Advanced Configuration

### Custom Voice (ElevenLabs)

1. Go to https://elevenlabs.io/voice-lab
2. Clone a voice or create your own
3. Copy the voice ID
4. Update `ELEVENLABS_VOICE_ID` in `.env`

### Custom Wake Word

Currently uses "jarvis" - to customize:

1. Update `WAKE_WORD` in `.env`
2. Adjust `WAKE_WORD_SENSITIVITY` (0.0-1.0)
3. Note: Porcupine has limited wake word options
4. For full customization, train your own model

### Budget Alerts

To get notified when approaching budget:

1. Monitor cost metrics in UI
2. Set lower `DAILY_BUDGET_USD`
3. JARVIS will auto-switch to efficient mode at threshold

---

**Congratulations!** 🎉

You now have a fully functional AI voice assistant. Enjoy using JARVIS!
