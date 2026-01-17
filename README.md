# JARVIS Voice Agent for Windows 11

A fully voice-controlled Windows 11 personal assistant using an intelligent dual-mode architecture that defaults to premium voice experience (gpt-4o-realtime-preview) while maintaining cost efficiency through smart fallback strategies.

## Quick Start

### Prerequisites

Before installing, ensure you have:

1. **Node.js 18+** - [Download](https://nodejs.org/)
2. **SoX (Sound eXchange)** - Required for audio capture
   ```bash
   # Using Chocolatey (recommended)
   choco install sox

   # Or download manually from: https://sourceforge.net/projects/sox/
   # Add to PATH after installation
   ```
3. **Visual C++ Build Tools** - Required for native modules
   ```bash
   npm install -g windows-build-tools
   # Or install Visual Studio with C++ workload
   ```
4. **OpenAI API Key** - [Get yours here](https://platform.openai.com/api-keys)
   - Requires access to: gpt-4o-realtime-preview, whisper-1, gpt-4o-mini

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/NicoLafakis/WhisperApp.git
cd WhisperApp

# 2. Install dependencies
npm install

# 3. Build the application
npm run build

# 4. Start JARVIS
npm start
```

### First Run Setup

1. On first launch, JARVIS will open the **Settings** window
2. Paste your **OpenAI API key** (required)
3. Optionally add **ElevenLabs API key** for premium voice
4. Configure budget limits and startup preferences
5. Click **Get Started**

That's it! JARVIS is now listening and ready to help.

---

## Overview

JARVIS is an always-listening, hands-free voice assistant that combines the power of OpenAI's Realtime API with a cost-efficient fallback chain. Zero touchpoints required after startup—JARVIS is always ready.

### Key Features

- **Always Listening**: No wake word needed - just start talking
- **Dual-Mode Architecture**: Premium (gpt-4o-realtime) for quality, Efficient (Whisper → GPT-4o-mini → ElevenLabs) for cost savings
- **Smart Cost Management**: Adaptive routing based on budget, time of day, and usage patterns
- **Full Windows Control**: Launch apps, manage files, control settings, and more through natural voice commands
- **Low Latency**: 300ms-2s response time depending on mode
- **Beautiful UI**: Modern Electron-based interface with real-time status and cost tracking
- **Light/Dark Mode**: Automatically matches your system preferences
- **Auto-Start**: Optionally run JARVIS when Windows starts

### Performance Metrics

| Metric | Target | Status |
|--------|--------|--------|
| Latency (Premium) | 300-800ms | ✓ |
| Latency (Efficient) | 1.5-2.5s | ✓ |
| Monthly Cost | $15-30 | ✓ |
| Voice Quality | 8-9/10 | ✓ |
| Reliability | 99.5% | ✓ |

---

## Usage

### Basic Operation

1. **Launch JARVIS**: Double-click the app or run `npm start`
2. **System Tray**: JARVIS runs in the system tray (bottom-right corner)
3. **Speak Naturally**: JARVIS is always listening - just talk!
4. **Click Tray Icon**: Toggle the main window visibility

### Example Commands

#### Application Control
- "Open Visual Studio Code"
- "Launch Chrome and go to GitHub"
- "Close all Chrome windows"
- "Minimize all windows"

#### File Operations
- "Show me the files in my Documents folder"
- "Create a new file called notes.txt"
- "Move all PDFs from Downloads to Documents"
- "Read the contents of config.json"

#### System Information
- "What's my system status?"
- "How much memory am I using?"
- "What time is it?"
- "Show me running processes"

#### Settings
- "Set volume to 50%"
- "What's the weather?" (opens browser)

---

## Configuration

### Settings UI

Access settings by clicking the gear icon in the JARVIS window:

- **API Keys**: Configure OpenAI and ElevenLabs credentials
- **Budget Limits**: Set daily and monthly spending caps
- **Startup Options**: Auto-start with Windows, skip settings screen

### Environment Variables (Advanced)

For advanced configuration, create a `.env` file:

```env
# API Keys (can also be set in UI)
OPENAI_API_KEY=sk-...
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=EXAVITQu4MsJ5X4xQvF9

# Budget (USD)
DAILY_BUDGET_USD=1.00
MONTHLY_BUDGET_USD=30.00

# Mode
DEFAULT_MODE=premium  # or efficient
PEAK_HOURS_START=9    # 9 AM
PEAK_HOURS_END=17     # 5 PM

# Audio
SAMPLE_RATE=16000
AUDIO_CHANNELS=1
```

---

## Cost Management

JARVIS intelligently manages costs through several strategies:

### Adaptive Routing

The router automatically switches between modes based on:

1. **Budget Limits**: Switches to efficient mode when daily budget reaches 50%
2. **Time of Day**: Uses efficient mode outside peak hours (9 AM - 5 PM)
3. **Interaction Type**: Simple queries use efficient mode

### Cost Breakdown

**Premium Mode (gpt-4o-realtime):**
- Cost: ~$0.12 per interaction
- Latency: 300-800ms
- Quality: 9/10

**Efficient Mode (Whisper → GPT-4o-mini → ElevenLabs):**
- Cost: ~$0.004 per interaction
- Latency: 1.5-2.5s
- Quality: 7/10

---

## Development

### Project Structure

```
WhisperApp/
├── src/
│   ├── main/              # Electron main process
│   │   ├── engine/        # Core engine components
│   │   ├── services/      # API clients
│   │   ├── functions/     # System functions
│   │   ├── preload.ts     # Secure IPC bridge
│   │   ├── JarvisEngine.ts
│   │   └── main.ts
│   ├── renderer/          # React UI
│   │   ├── App.tsx
│   │   ├── SettingsModal.tsx
│   │   └── styles.css
│   └── shared/            # Shared types & utilities
├── assets/                # Application icons
├── scripts/               # Build scripts
├── package.json
└── README.md
```

### Building

```bash
# Development (hot reload)
npm run dev

# Production build
npm run build

# Create Windows installer
npm run package
```

### Testing

```bash
npm test
npm run test:coverage
```

---

## Troubleshooting

### SoX Not Found

If you get "SoX not found" errors:

1. Install SoX: `choco install sox`
2. Restart your terminal/IDE
3. Verify installation: `sox --version`
4. If still failing, add SoX to your PATH manually

### Native Module Errors

If `npm install` fails on native modules:

1. Install Visual C++ Build Tools
2. Run: `npm install -g windows-build-tools`
3. Delete `node_modules` and `package-lock.json`
4. Run `npm install` again

### Audio Not Working

- Check that your microphone is enabled and set as default
- Verify audio permissions in Windows settings
- Restart JARVIS after connecting new audio devices

### API Errors

- Verify your API keys are correct in Settings
- Check that you have access to the required OpenAI models
- Monitor your OpenAI and ElevenLabs usage/quotas

### High Costs

- Lower daily/monthly budget in Settings to force efficient mode
- Adjust usage during non-peak hours

---

## Architecture

```
┌─────────────────────────────────────┐
│      JARVIS Electron App            │
│                                     │
│  ┌───────────────────────────────┐  │
│  │  React UI + System Tray       │  │
│  └───────────────────────────────┘  │
└─────────────┬───────────────────────┘
              │
              ↓
┌─────────────────────────────────────┐
│      Voice Input Layer              │
│  • Audio Capture (16kHz PCM)        │
│  • Always Listening Mode            │
└─────────────┬───────────────────────┘
              │
              ↓
┌─────────────────────────────────────┐
│      Adaptive Router                │
│  • Cost Tracking                    │
│  • Mode Selection                   │
└─────────┬───────────────────────────┘
          │
    ┌─────┴─────┐
    ↓           ↓
┌─────────┐  ┌──────────┐
│ PREMIUM │  │ EFFICIENT│
│  MODE   │  │   MODE   │
│         │  │          │
│ Realtime│  │ Whisper  │
│   API   │  │    +     │
│         │  │ GPT-4o   │
│         │  │    +     │
│         │  │ElevenLabs│
└─────────┘  └──────────┘
     │            │
     └─────┬──────┘
           ↓
┌─────────────────────────────────────┐
│   Function Execution Layer          │
│  • Windows System Integration       │
│  • File Operations                  │
│  • Application Control              │
└─────────────────────────────────────┘
```

---

## Security

JARVIS implements several security measures:

- **Context Isolation**: Renderer process is isolated from Node.js
- **Secure IPC**: Only whitelisted methods exposed to UI
- **Path Validation**: File operations restricted to safe directories
- **Command Filtering**: Dangerous system commands blocked
- **Confirmation Prompts**: Destructive operations require approval

---

## Available Functions

JARVIS supports 14 built-in functions:

### Application Control
- `launch_application` - Launch apps
- `open_file` - Open files with default app
- `manage_window` - Minimize/maximize/close/focus windows

### File Operations
- `list_files` - List directory contents
- `create_file` - Create new files
- `read_file` - Read file contents
- `delete_file` - Delete files (requires confirmation)
- `move_file` - Move/rename files
- `search_files` - Search for files

### System
- `execute_command` - Run PowerShell commands (restricted)
- `query_system_state` - Get CPU/memory/process info
- `query_time_date` - Get current time/date
- `set_volume` - Adjust system volume
- `open_url` - Open URLs in browser

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

MIT License - see LICENSE file for details

## Credits

- Built with [Electron](https://www.electronjs.org/)
- Powered by [OpenAI](https://openai.com/)
- Voice synthesis by [ElevenLabs](https://elevenlabs.io/)

---

**Made with care by the JARVIS team**
