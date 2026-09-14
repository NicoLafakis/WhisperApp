# Whisper to Jarvis: Windows voice commands

> Superseded September 13, 2026: the user selected a separate application named
> **Jarvis Protocol**, for personal Windows use. The authoritative build packet is
> [Jarvis Protocol](../../JarvisProtocol/README.md). This earlier proposal is retained
> as concept history; its in-app mode and client-delegation recommendations are not
> the current build specification.

Status: proposal, September 13, 2026. The transcription upgrade is implemented;
the assistant below is proposed work. Priority confirmed by the user: voice commands
across Windows apps.

## Recommended product

Keep the existing hold-to-dictate shortcut. Add a separate configurable shortcut
that toggles a Jarvis conversation, with an obvious listening indicator, captions,
task progress, and a Stop button. Ordinary dictation stays literal. In Jarvis mode,
the user can say "Open Notepad", "Switch to Chrome", or "Make this selected text
shorter and put the revision on my clipboard" and hear a result grounded in what
the app actually did. Start with explicit activation; add a local wake word later.

Within an active Jarvis session, spoken input has two outcomes: an actionable command
is delegated for execution and acknowledged aloud with its verified result; all other
input is conversational and receives an audible response. No command prefix is needed.
For an ambiguous action, ask a short spoken clarification before execution. A statement
such as "I wonder whether I should delete that" is conversation, not authorization.
The separate dictation shortcut remains the explicit way to enter literal text.

For example: "Open Notepad" opens it and receives an audible acknowledgement;
"What should I work on next?" receives a spoken answer; "Close that" with multiple
possible targets receives a spoken clarification. Captions complement spoken output.

Use GPT-Live 1 for spoken interaction and a backend agent for Windows actions.
GPT-Live can listen while speaking and delegate work. The application still owns
tool execution, authorization, and task state. Stopping speech does not itself cancel
a task. [OpenAI GPT-Live guide](https://developers.openai.com/api/docs/guides/live)

## What this repository provides

| Existing component | Reuse and required change |
| --- | --- |
| `main.py` tray app, Qt signals, recording indicator, worker | Keep the shell; add a session controller and command overlay. Its current recording/transcribing flags cannot represent overlapping speech and tasks. |
| `hotkey_listener.py` | Retain dictation; add a distinct assistant toggle and stop control without registering conflicting hooks. |
| `audio_recorder.py` | Keep bounded 16 kHz WAV capture for dictation. Add a separate streaming input/output path, device recovery, playback buffering, and echo handling for conversation. |
| `transcription_service.py` | Keep GPT Transcribe for completed recordings. GPT-Live needs a persistent connection, not this file-upload worker. |
| `text_inserter.py` | Reuse only after adding target-window validation and clipboard restoration. It currently pastes into whichever window is focused at completion. |
| `config_manager.py`, `settings_dialog.py` | Reuse preferences; add assistant shortcut, audio output, allowed apps, usage controls, and model settings. |

There is currently no agent, Windows action registry, speech playback, persistent
conversation, task store, or app automation adapter in the source. A model switch
alone cannot supply these capabilities.

## Proposed architecture

Qt tray/overlay → Jarvis session controller ↔ GPT-Live audio connection.
Delegated requests → local agent coordinator → validated Windows tools → verified
results → spoken response and visible action history.

Prefer client delegation for local execution control. Start with a native WebSocket
audio spike to establish latency, interruption behavior, and echo performance before
committing to that transport. If speaker echo is unacceptable, evaluate a WebRTC media
layer. Keep credentials in the native trusted process, never an embedded web page.
GPT-Live supports both connection paths. [Connection guide](https://developers.openai.com/api/docs/guides/live)

Implement separate session and task states: disconnected/connecting/listening and
queued/running/awaiting-confirmation/completed/failed/cancelled. Track speaking from
actual playback. A disconnect must not silently repeat a completed action. Use task
IDs and persist execution receipts locally; reject stale results after cancellation.

## First useful Windows tool set

| Tool | Behavior and evidence |
| --- | --- |
| Open an allowed app | Resolve a configured executable; launch with structured arguments; verify a matching window exists. |
| Find/switch window | Enumerate titles and process identities; clarify ambiguous matches; verify foreground window. |
| Read selected text | Explicit user request; use an app adapter or carefully managed clipboard capture; preserve clipboard. |
| Rewrite selection | Backend returns a revision; preview or copy it; replace only after rechecking the original window and selection. |
| Type into target | Bind the operation to a window identity; stop if focus or content changed; avoid blind global paste. |

Use app APIs where available and Windows UI Automation for supported controls.
Pilot Notepad and a browser with explicit supported flows. Arbitrary cross-app
automation is a later expansion: elevated apps, custom controls, and inaccessible
interfaces need individual adapters or a separately evaluated visual-control path.
Do not expose unrestricted shell execution as the initial Windows tool.

The executor validates tool arguments and app access outside the model. Sending
messages, submitting forms, deleting files, or making purchases requires a concrete
confirmation for that action. Opening an allowed app or switching windows should be
immediate. Treat text read from windows and documents as data, not authority to run
more commands. Keep a visible action history and a global cancellation control.

## Delivery stages and acceptance gates

1. **Dictation upgrade (this change):** migrate defaults, preserve credentials and
   preferences, update language schema and selected-model key check. Offline tests
   cover migration and request behavior. Real microphone/API accuracy remains to be
   evaluated on representative user phrases.
2. **Conversation spike:** start/stop a GPT-Live session, hear a response, interrupt
   it, disconnect/reconnect, and release audio devices on exit. Measure latency and
   speaker echo on the actual Windows machine; report session usage.
3. **Windows command MVP:** open/switch apps and rewrite selected text with the
   tools above. Verify outcomes in the target app. Test ambiguous windows, focus
   changes, unavailable apps, denied actions, and network loss during execution.
   Test mixed command/conversation sessions: casual speech gets audible answers,
   commands get verified spoken results, and ambiguous actions get clarification.
4. **Workflow expansion:** add named app adapters, multi-step tasks, opt-in context
   and memory, then optional wake-word activation. Add each workflow with an end-state
   check and cancellation behavior.

Each stage is a separate deliverable. Most implementation effort is in audio lifecycle
and dependable app control; estimates should follow the conversation spike and a
specific list of target applications. A universal desktop assistant is substantially
larger than the initial five-tool MVP.

## Operating cost and remaining decisions

GPT-Live costs $0.05 per connected minute, plus backend model/tool usage: a 30-minute
session is $1.50 before backend charges. Close idle sessions and show elapsed usage;
eight connected hours would be $24 before backend charges.
[Model pricing](https://developers.openai.com/api/docs/models/gpt-live-1)

GPT Transcribe costs $0.0045 per audio minute, about $0.27 for one hour of dictation.
[Transcription pricing](https://developers.openai.com/api/docs/models/gpt-transcribe)

Before the command MVP, select the first three real workflows and target apps,
the assistant shortcut, and which actions may execute immediately. Choose a backend
model after evaluating those tool-selection tasks for accuracy and latency. Screen
context and persistent memory should be explicit opt-ins with retention controls.
