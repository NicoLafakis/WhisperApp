# WhisperApp Reverse-Engineered PRD

Status: Inferred from the shipped Windows binary `WhisperApp.exe` in this repository.

Provenance:
- Binary analyzed on March 13, 2026.
- File on disk: `WhisperApp.exe`, last modified December 11, 2025.
- Packaging/runtime: PyInstaller one-file bundle, Python 3.13, PyQt5 UI.
- This document reflects observed behavior from bytecode/disassembly, not original source or original product docs.

## 1. Product Summary

WhisperApp is a Windows system tray utility for push-to-talk speech transcription. A user holds a keyboard shortcut to record microphone audio, releases the shortcut to stop recording, and the app sends the captured audio to OpenAI Whisper for transcription. The resulting text is pasted into the currently focused application and may also be shown in a notification.

The product is optimized for lightweight background use:
- No primary main window.
- Persistent tray icon with a small context menu.
- Minimal setup flow centered on entering an OpenAI API key.

## 2. Target User

Primary user:
- A Windows user who wants fast dictation into any text field without switching applications.

Likely use cases:
- Writing messages, notes, emails, or documents by voice.
- Dictating short snippets while keeping hands on the keyboard.
- Using speech as a faster replacement for manual typing in arbitrary desktop apps.

## 3. Core User Journey

1. User launches the app.
2. App starts in the system tray and shows a startup notification.
3. If no API key is configured, the app shows a welcome dialog instructing the user to open Settings.
4. User opens Settings from the tray menu and enters an OpenAI API key.
5. User holds `Ctrl+Shift+Space` to begin recording.
6. While the keys are held, the app records microphone audio.
7. When the keys are released, the app stops recording and begins transcription.
8. App sends the recorded WAV file to the OpenAI transcription endpoint.
9. App pastes the returned text into the active application using simulated `Ctrl+V`.
10. App optionally shows a completion notification.

## 4. Current Feature Set

### 4.1 Tray App

The app runs as a tray-only application with these menu items:
- `Status: Ready` (disabled status label)
- `Settings`
- `About`
- `Quit`

Startup behavior:
- Tray icon is shown immediately.
- App shows a tray toast: `WhisperApp Started` / `Press Ctrl+Shift+Space to start transcription`.

### 4.2 Settings Dialog

The settings dialog includes:
- API key input
- Model selector
- Language selector
- Read-only hotkey field
- `Automatically copy to clipboard` checkbox
- `Show notifications` checkbox
- `Test API Key` button
- `Save` and `Cancel` buttons

Model options currently exposed:
- `whisper-1`

Language options currently exposed:
- Auto Detect (`""`)
- English (`en`)
- Spanish (`es`)
- French (`fr`)
- German (`de`)
- Italian (`it`)
- Portuguese (`pt`)
- Russian (`ru`)
- Japanese (`ja`)
- Korean (`ko`)
- Chinese (`zh`)

Hotkey UX:
- The dialog shows a hotkey field and stores a hotkey value.
- The field is read-only.
- A note in the UI says customization is "coming soon".

### 4.3 API Key Management

API key sources:
- First preference: encrypted value in app config
- Fallback: environment variable `WHISPER_API_KEY`

If `WHISPER_API_KEY` is present and config is empty, the app stores it into config.

API key test flow:
- Settings dialog creates an `OpenAI` client.
- Validation is done by calling `client.models.list()`.
- Success shows `API Key Valid`.
- Failure shows `API Key Error` with the exception string.

### 4.4 Audio Recording

Recording implementation details:
- Microphone input via `pyaudio`
- Mono audio
- 16-bit PCM (`paInt16`)
- 16 kHz sample rate
- Buffer size: 1024 frames

Recording UX:
- On shortcut press: status changes to `Status: Recording...`
- App shows `Recording Started` / `Speak now... Release keys to transcribe`
- On shortcut release: status changes to `Status: Transcribing...`

Temporary file behavior:
- Audio is written to `%TEMP%\\whisperapp\\recording.wav`
- The same filename is reused rather than uniquely generated per recording

### 4.5 Transcription

Transcription implementation:
- Uses the OpenAI Python SDK
- Creates an `httpx.Client(timeout=60.0, follow_redirects=True)`
- Calls `client.audio.transcriptions.create(...)`

Inputs sent:
- `model`
- `file`
- `language` only when non-empty

Outputs handled:
- Uses `transcript.text.strip()`
- If no client is configured, returns `Error: API key not configured`
- Exceptions are surfaced as `Error: {exception}`

### 4.6 Text Output

Post-transcription behavior:
- If `auto_copy` is enabled, app first copies the transcript to clipboard.
- App then always attempts insertion by:
  - waiting 100 ms
  - copying transcript to clipboard
  - simulating `Ctrl+V`

Practical result:
- Transcript is pasted into the active focused field.
- Clipboard contents end up replaced by the transcript.

### 4.7 Notifications

The app uses tray notifications for:
- Startup
- Missing API key
- Recording started
- No audio recorded
- Transcription errors
- Settings updated
- Transcription complete

Important nuance:
- The `show_notifications` setting only gates the final success notification after transcription.
- Several other notifications still occur regardless of that setting.

## 5. Configuration Model

Config directory:
- `%USERPROFILE%\\.whisperapp`

Files:
- `config.json`
- `key.key`

Stored settings and defaults:
- `api_key`: `""`
- `model`: `"whisper-1"`
- `language`: `"en"`
- `hotkey`: `"ctrl+shift+space"`
- `auto_copy`: `true`
- `show_notifications`: `true`
- `audio_device`: `"default"`

Security model:
- `api_key` is encrypted with Fernet before being written to `config.json`.
- The Fernet key is stored locally in `key.key` in the same app directory.

Security implication:
- This protects against casual plaintext exposure in config files.
- It does not protect against a local user or process that can read both files.

## 6. Recovered Functional Requirements

### FR-1 Startup

The app shall launch as a tray application and remain running when no windows are open.

### FR-2 Onboarding

If no API key is configured, the app shall prompt the user to configure one via Settings.

### FR-3 Push-to-Talk Recording

The app shall begin recording when the user presses `Ctrl+Shift+Space` and shall stop when the key combination is released.

Observed implementation note:
- The current build listens specifically for `space` press/release and separately checks whether `ctrl` and `shift` are pressed.

### FR-4 Transcription Request

After recording stops, the app shall send the recorded WAV file to OpenAI transcription using the configured model and language.

### FR-5 Text Insertion

After a successful transcription, the app shall insert the transcribed text into the currently active application.

### FR-6 Clipboard Support

The app shall copy the transcript to the clipboard as part of the insertion flow.

### FR-7 Settings Persistence

The app shall persist configuration locally across launches.

### FR-8 Validation

The app shall allow the user to verify that the configured API key is accepted by OpenAI.

### FR-9 Status Visibility

The app shall expose coarse-grained state through the tray menu:
- Ready
- Recording
- Transcribing

## 7. Known Gaps, Constraints, and Product Debt

### 7.1 Hotkey Customization Is Not Actually Implemented

The config contains a `hotkey` value and the UI displays it, but the current runtime behavior is still hardcoded to the `space` key combined with `ctrl` and `shift`.

Implication:
- Changing the stored hotkey value does not change runtime behavior.

### 7.2 `audio_device` Exists in Config but Is Unused

The config schema includes `audio_device`, but no recovered UI or main flow uses it.

Implication:
- The shipped product appears to have incomplete groundwork for microphone selection.

### 7.3 `auto_copy` Does Not Prevent Clipboard Overwrite

Even when `auto_copy` is disabled, insertion still works by copying the transcript to the clipboard and pasting with `Ctrl+V`.

Implication:
- The clipboard is effectively overwritten on every successful transcription.

### 7.4 Notification Setting Has Partial Coverage

`show_notifications` only controls the success notification after transcription. Other notifications are still emitted.

### 7.5 No Local/Offline Transcription Path

Despite the product name, the current implementation is cloud-backed OpenAI transcription. There is no local inference engine in the shipped binary.

### 7.6 Limited Model Flexibility

The settings UI only exposes `whisper-1`.

### 7.7 Active-Window Insertion Is Best-Effort

Text insertion depends on:
- Focus being in the intended text field
- Simulated `Ctrl+V` working in the target app
- Global keyboard access on Windows

Implication:
- Insertion can fail or paste into the wrong target if focus changes.

### 7.8 Single Temporary Filename

Recorded audio is always written to the same temp filename.

Implication:
- Concurrent recordings are not supported.
- Crash recovery and forensic inspection are limited.

## 8. Non-Functional Characteristics

Platform assumptions:
- Windows desktop app
- Global keyboard hooks
- System tray available
- Microphone available
- Internet access required for transcription

Performance expectations inferred from behavior:
- Record/stop interaction should feel immediate.
- Transcription runs on a worker thread so the tray UI remains responsive.

Failure handling:
- Errors are surfaced mainly through tray notifications and message boxes.
- There is no evidence of retry logic, offline queueing, or structured telemetry.

## 9. Recovered Component Map

Recovered logical modules from the binary:
- `main`: application bootstrap, tray, hotkeys, orchestration
- `config_manager`: config persistence and API key encryption
- `audio_recorder`: microphone capture and WAV file creation
- `transcription_service`: OpenAI client creation and transcription call
- `text_inserter`: clipboard copy and synthetic paste
- `settings_dialog`: settings UI and API key validation

This is the effective architecture to preserve if the app is rebuilt from source.

## 10. Recommended PRD Baseline for Future Changes

If this product is continued, the next-source-of-truth PRD should preserve these current behaviors unless deliberately changed:
- Tray-first, low-friction workflow
- Press-to-record, release-to-transcribe interaction
- Cross-app text insertion as the primary success path
- Minimal settings surface
- Explicit API key setup flow

The first deliberate product decisions worth making are:
- Whether hotkeys should become fully configurable
- Whether clipboard overwrite is acceptable
- Whether microphone selection should be exposed
- Whether success notifications should be globally suppressible
- Whether the app should support local/offline transcription
- Whether the app should support newer OpenAI speech-to-text models/endpoints

## 11. Open Questions

These could not be confirmed from the binary alone:
- Whether the original roadmap included additional models
- Whether local transcription was planned but never shipped
- Whether clipboard preservation was intentionally sacrificed for simplicity
- Whether `audio_device` was partially implemented or abandoned
- Whether enterprise/error telemetry existed outside the binary
