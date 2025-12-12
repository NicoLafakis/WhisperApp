# JARVIS Voice Agent - AI Coding Instructions

## Architecture Overview

This is an **Electron + React + TypeScript** voice assistant with a dual-mode architecture:
- **Premium Mode**: OpenAI Realtime API (gpt-4o-realtime) - 300-800ms latency, ~$0.12/interaction
- **Efficient Mode**: Whisper → GPT-4o-mini → ElevenLabs chain - 1.5-2.5s latency, ~$0.004/interaction

The system intelligently switches modes based on budget thresholds, time of day, and interaction complexity via `AdaptiveRouter`.

## Project Structure

```
src/
├── main/              # Electron main process
│   ├── JarvisEngine.ts    # Core orchestrator - coordinates all components
│   ├── engine/            # Audio pipeline & routing logic
│   │   ├── AdaptiveRouter.ts   # Mode switching decisions
│   │   ├── CostTracker.ts      # Budget monitoring
│   │   └── WakeWordDetector.ts # Local Porcupine wake word
│   ├── services/          # API clients
│   │   ├── RealtimeClient.ts   # WebSocket to OpenAI Realtime
│   │   └── FallbackChain.ts    # Whisper + GPT + ElevenLabs
│   └── functions/         # Windows system integration
│       ├── index.ts           # Function definitions (OpenAI tool format)
│       └── executor.ts        # PowerShell execution with security
├── renderer/          # React frontend (Vite)
└── shared/            # Cross-process types & utilities
    ├── types/index.ts     # All TypeScript interfaces
    └── utils/config.ts    # Environment-based configuration
```

## Key Patterns

### Dual-Mode Routing Logic
The `AdaptiveRouter` determines mode using this priority:
1. User forced mode (via `setForcedMode()`)
2. Budget threshold exceeded (>50% daily) → efficient
3. Outside peak hours (before 9am or after 5pm) → efficient
4. Simple interaction type → efficient
5. Default to configured mode

### Function Definitions
Functions in [src/main/functions/index.ts](../src/main/functions/index.ts) follow OpenAI's tool calling schema. Add new Windows integrations there:
```typescript
{
  name: 'function_name',
  description: 'What it does',
  parameters: { type: 'object', properties: {...}, required: [...] }
}
```

### Security Model
`FunctionExecutor` implements three-tier security:
- **Blocked functions**: Listed in config, always denied
- **Confirmation required**: Prompts user before execution (e.g., `delete_file`)
- **Dangerous patterns**: Regex blocklist for destructive PowerShell commands

### Type Definitions
All shared types live in [src/shared/types/index.ts](../src/shared/types/index.ts). Key types:
- `AgentMode`: `'premium' | 'efficient'`
- `AgentStatus`: `'idle' | 'listening' | 'thinking' | 'speaking' | 'executing' | 'error'`
- `RoutingDecision`: Contains mode, reason, estimated cost/latency

## Development Commands

```bash
npm run dev          # Run both renderer (Vite) and main process concurrently
npm run build        # Build renderer + transpile main process
npm run test         # Jest unit tests
npm run test:watch   # Jest in watch mode
npm run type-check   # TypeScript validation without emit
```

## Testing Conventions

Tests live in `tests/unit/` with `.test.ts` suffix. Pattern from [AdaptiveRouter.test.ts](../tests/unit/AdaptiveRouter.test.ts):
- Use `jest.spyOn(Date.prototype, 'getHours')` to mock time-based routing
- Call `jest.restoreAllMocks()` in both `beforeEach` and `afterEach`
- Test routing decisions by manipulating `CostTracker` state

## Environment Variables

Required in `.env`:
- `OPENAI_API_KEY` - For Realtime API, Whisper, and GPT
- `ELEVENLABS_API_KEY` - For fallback TTS
- `ELEVENLABS_VOICE_ID` - Voice selection (default: `EXAVITQu4MsJ5X4xQvF9`)

Optional routing config:
- `DEFAULT_MODE` - `premium` or `efficient`
- `DAILY_BUDGET_USD` - Triggers efficient mode when exceeded (default: 1.00)
- `PEAK_HOURS_START/END` - Hours using premium mode (default: 9-17)

## Cost Tracking

`CostTracker` monitors spending. Record costs using typed methods:
- `recordRealtimeUsage(inputTokens, outputTokens)` - Premium mode
- `recordWhisper(audioSeconds)` - Efficient mode transcription
- `recordGPT(inputTokens, outputTokens)` - Efficient mode reasoning  
- `recordElevenLabs(characters)` - Efficient mode TTS
