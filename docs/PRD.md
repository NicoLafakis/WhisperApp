# WhisperApp — Product Requirements Document

**Version:** 1.0.0  
**Status:** Draft — Ready for Implementation  
**Target Platform:** Windows 10/11 (x64)  
**Distribution:** PyInstaller one-file `.exe` + optional installer  

---

## 1. Product Overview

WhisperApp is a Windows system-tray utility that provides push-to-talk speech transcription. The user holds a configurable keyboard shortcut to record microphone audio, releases it to stop, and the app sends the audio to OpenAI's Whisper API for transcription. The resulting text is inserted into the currently focused application via clipboard paste.

### 1.1 Design Principles

- **Invisible:** No main window. The app lives in the system tray and stays out of the way.
- **Fast:** Record-to-text latency should feel instantaneous; transcription happens on a background thread.
- **Reliable:** Graceful degradation when the API is unavailable, the mic is unplugged, or hotkeys require elevation.
- **Minimal:** The smallest possible settings surface. One API key, one hotkey, one model.

### 1.2 Success Metrics

- App launches successfully on a clean Windows 11 machine with Python dependencies installed.
- Push-to-talk recording starts within 200 ms of shortcut press.
- Transcription round-trip (release → text inserted) completes within 5 seconds for a 10-second utterance on a typical broadband connection.
- Zero unhandled exceptions during normal operation.

---

## 2. Target User

**Primary:** Windows knowledge workers who want to dictate into any text field without switching applications.

**Typical scenarios:**
- Writing emails, Slack messages, or notes.
- Filling out forms or documents.
- Coding by voice (short identifiers, comments).

**Technical comfort:** Low-to-moderate. The user can copy-paste an API key but should not need to edit JSON or use a terminal.

---

## 3. Core User Journey

| Step | Action | System Response |
|------|--------|-----------------|
| 1 | User launches the app. | App appears in the system tray. Toast: *"WhisperApp Started — Press Ctrl+Shift+Space to start transcription."* |
| 2 | (First run) No API key is configured. | Toast: *"API Key Required"*. After 800 ms, a welcome dialog opens. |
| 3 | User opens **Settings** from the tray menu. | Settings dialog appears. |
| 4 | User pastes an OpenAI API key and clicks **Test API Key**. | Dialog shows *"API Key Valid"* or *"API Key Error"*. |
| 5 | User clicks **Save**. | Settings are persisted. Toast: *"Settings Updated"*. |
| 6 | User holds **Ctrl+Shift+Space**. | The indicator immediately shows *"OPENING MIC"*. Once capture starts, a red waveform responds to the microphone level while it shows *"RECORDING"*. |
| 7 | User releases the shortcut. | The indicator remains visible through *"SAVING"* and *"PROCESSING"*. Its waveform stops moving, elapsed time advances, and GPT Transcribe may show a partial preview. A transient upload error changes the state to *"RETRYING"* until the next attempt. |
| 8 | Transcription completes. | If the original target still has focus, text is pasted via `Ctrl+V`; otherwise the completed result is copied when automatic copy is enabled and remains available in Dictation History. Toast: *"Transcription Complete"* (if enabled). |
| 9 | User right-clicks the tray icon and selects **Quit**. | App exits cleanly, releasing all hooks and audio resources. |

---

## 4. Functional Requirements

### FR-1. Tray Application Lifecycle

- **FR-1.1** The app shall launch as a tray-only application with no persistent main window.
- **FR-1.2** The app shall remain running when all windows are closed (`setQuitOnLastWindowClosed(False)`).
- **FR-1.3** The tray icon shall be a 64×64 programmatically drawn icon (blue circle, white "W" letter).
- **FR-1.4** The tray context menu shall contain:
  - `Status: <state>` (disabled label)
  - `Settings`
  - `About`
  - `Quit`
- **FR-1.5** On startup, the app shall show a tray notification with title *"WhisperApp Started"* and message *"Press Ctrl+Shift+Space to start transcription"*.
- **FR-1.6** If the system tray is not available, the app shall show a critical error dialog and exit with code `1`.

### FR-2. Onboarding & API Key Management

- **FR-2.1** If no API key is configured at startup, the app shall show a toast *"API Key Required"* and, after a short delay, a welcome dialog prompting the user to open Settings.
- **FR-2.2** The API key shall be stored encrypted with Fernet in `config.json`.
- **FR-2.3** The Fernet key shall be stored in `key.key` in the same config directory (`%USERPROFILE%\.whisperapp`).
- **FR-2.4** If the environment variable `WHISPER_API_KEY` is set and the config key is empty, the app shall copy the env key into config on startup.
- **FR-2.5** The Settings dialog shall allow the user to test the API key by calling `client.models.list()`.
- **FR-2.6** Invalid or corrupted config files shall be silently reset to defaults rather than crashing.

### FR-3. Push-to-Talk Recording

- **FR-3.1** The default hotkey shall be `Ctrl+Shift+Space`.
- **FR-3.1a** Before a global hotkey press starts capture on Windows, the listener shall confirm the modifiers are currently held, so stale hook state cannot open the microphone.
- **FR-3.2** Recording shall start when `space` is pressed while `ctrl` and `shift` are held.
- **FR-3.3** Recording shall stop when `space` is released.
- **FR-3.4** The app shall prevent concurrent audio captures while allowing a new recording to begin while an earlier recording is being transcribed.
- **FR-3.5** Audio shall be captured as:
  - Mono, 16-bit PCM (`paInt16`), 16 kHz sample rate, 1024-frame buffer.
- **FR-3.6** Recorded audio shall be written to `%TEMP%\whisperapp\recording.wav`.
- **FR-3.7** If no audio frames were captured, the app shall abort transcription and show a *"No Audio Recorded"* notification.
- **FR-3.8** The audio recorder shall use `threading.Lock` for thread-safe start/stop and `threading.Event` for the recording loop.
- **FR-3.9** Opening and stopping the audio device shall run outside the Qt UI thread. Hotkey press and release shall return to the UI immediately; a release received during device startup shall stop recording as soon as startup completes.
- **FR-3.10** The indicator shall show explicit microphone opening, recording, saving, processing, queued, and retrying states. A red waveform shall respond to actual microphone level during recording and stop moving after capture. The indicator shall show elapsed time and remain visible until insertion, a recoverable text result, or failure is reported.
- **FR-3.11** Fresh pending dictations shall be transcribed before older due retries, with a foreground worker that can run while an older retry remains in flight. Background retries shall wait during active capture; all saved recordings remain durable for later retry.
- **FR-3.12** Completed-take retention scans shall not delay opening the microphone or finalizing audio.

### FR-4. Transcription

- **FR-4.1** Transcription shall run on a `QThread` worker to keep the UI responsive.
- **FR-4.2** The app shall use the OpenAI Python SDK with an `httpx.Client(timeout=60.0)`.
- **FR-4.3** The request shall include:
  - `model` (from settings)
  - `file` (the WAV file handle)
  - `language` (only if non-empty)
- **FR-4.4** If the API key is not configured, the worker shall return `"Error: API key not configured"`.
- **FR-4.5** Any API or network exception shall be caught and returned as `"Error: {exception}"`.
- **FR-4.6** The main thread shall receive the result via a `pyqtSignal(str)`.
- **FR-4.7** For GPT Transcribe, the app shall display streamed text deltas while the service processes the uploaded, completed recording. The partial text is a preview; only the final result is saved as completed and eligible for paste. `whisper-1` continues to use a non-streaming request.
- **FR-4.8** This file-upload flow does not provide live transcription while the microphone is recording. Live partial text is possible through a separate Realtime transcription session and requires its own audio streaming, target-field update, and finalization behavior.

### FR-5. Text Insertion

- **FR-5.1** On successful transcription, the app shall:
  1. Copy the text to the clipboard (if `auto_copy` is enabled).
  2. Wait 100 ms.
  3. Copy the text to the clipboard again.
  4. Simulate `Ctrl+V` via the `keyboard` module.
- **FR-5.2** If the result is empty or starts with `"Error:"`, the app shall show a *"Transcription Error"* notification and skip insertion.
- **FR-5.3** The insertion is best-effort; the app does not guarantee focus has not shifted.
- **FR-5.4** If a successful transcript is not pasted because focus changed, it shall replace the clipboard when automatic copy is enabled. A failed transcript shall leave the clipboard unchanged and clearly report that the audio is saved in Dictation History, so an older clipboard value is not presented as the new result.

### FR-6. Settings Dialog

- **FR-6.1** The dialog shall be a modal `QDialog` with minimum width 440 px.
- **FR-6.2** Fields:
  - **OpenAI API Key** — password echo, placeholder `sk-...`
  - **Model** — dropdown, default `whisper-1`
  - **Language** — dropdown with Auto Detect + 10 languages
  - **Hotkey** — read-only text field showing current hotkey + *"Hotkey customization coming soon."*
  - **Automatically copy to clipboard** — checkbox
  - **Show notifications** — checkbox
- **FR-6.3** Buttons: `Test API Key`, `Save`, `Cancel`.
- **FR-6.4** On **Save**, settings are persisted, the transcription service is reconfigured, and a *"Settings Updated"* toast is shown.

### FR-7. Notifications

- **FR-7.1** The app shall use `QSystemTrayIcon.showMessage` for all notifications.
- **FR-7.2** Notifications shall be shown for:
  - Startup
  - Missing API key
  - Recording started
  - No audio recorded
  - Transcription errors
  - Settings updated
  - Transcription complete (gated by `show_notifications`)
- **FR-7.3** The `show_notifications` setting shall **only** control the *"Transcription Complete"* success toast. All other notifications are mandatory.
- **FR-7.4** Notification duration: 5000 ms.

### FR-8. Logging

- **FR-8.1** Logs shall be written to `%TEMP%\whisperapp\runtime.log` and mirrored to stdout.
- **FR-8.2** Log format: `%(asctime)s [%(levelname)s] %(message)s`
- **FR-8.3** Uncaught exceptions shall be logged via `sys.excepthook`.

### FR-9. Shutdown

- **FR-9.1** On application exit, the app shall:
  - Stop the hotkey listener (`keyboard.unhook`).
  - Terminate the audio recorder (stop stream, close stream, terminate PyAudio).
- **FR-9.2** Shutdown errors shall be logged but shall not prevent exit.

---

## 5. Configuration Schema

**Directory:** `%USERPROFILE%\.whisperapp`  
**Files:** `config.json`, `key.key`

```json
{
  "api_key": "<fernet-encrypted-string>",
  "model": "whisper-1",
  "language": "en",
  "hotkey": "ctrl+shift+space",
  "auto_copy": true,
  "show_notifications": true,
  "audio_device": "default"
}
```

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `api_key` | string | `""` | Encrypted with Fernet. Empty means unset. |
| `model` | string | `"whisper-1"` | Passed to OpenAI `audio.transcriptions.create`. |
| `language` | string | `"en"` | ISO-639-1 code. `""` = auto-detect. |
| `hotkey` | string | `"ctrl+shift+space"` | Stored for future use. Runtime is still hardcoded. |
| `auto_copy` | boolean | `true` | Copies text to clipboard before insertion. |
| `show_notifications` | boolean | `true` | Gates only the success notification. |
| `audio_device` | string | `"default"` | Reserved for future microphone selection. |

---

## 6. Non-Functional Requirements

### 6.1 Performance

- The Qt UI shall show the `STARTING` indicator and return from hotkey handling within 200 ms. Physical microphone activation depends on the Windows audio device and driver; device open must not block the UI.
- Transcription worker thread must not block the Qt event loop.
- Audio buffer underruns shall be handled gracefully (`exception_on_overflow=False`).

### 6.2 Reliability

- The app shall not crash if the microphone is unplugged during recording.
- The app shall not crash if the network is unavailable during transcription.
- Corrupted config files shall be reset to defaults automatically.

### 6.3 Security

- The API key shall never be written to disk in plaintext.
- The Fernet key is local-only and provides casual-observer protection, not cryptographic isolation from other local processes.

### 6.4 Compatibility

- **OS:** Windows 10 (1903+) and Windows 11.
- **Python:** 3.11+ (development), bundled via PyInstaller (distribution).
- **Privileges:** Global hotkeys may require Administrator on some enterprise policies. The app shall degrade gracefully (show a warning dialog) if hooks fail.

### 6.5 Accessibility

- The tray icon shall be visible in both light and dark Windows themes.
- Settings dialog shall support standard Windows keyboard navigation (Tab, Enter, Escape).

---

## 7. Architecture & Component Map

```
whisperapp/
├── __init__.py          # Package metadata (__version__)
├── __main__.py          # Entry point: imports main() and calls it
├── main.py              # WhisperTrayApp, TranscriptionThread, logging setup
├── config_manager.py    # ConfigManager: JSON + Fernet encryption
├── audio_recorder.py    # AudioRecorder: pyaudio capture + WAV output
├── transcription_service.py  # TranscriptionService: OpenAI client wrapper
├── text_inserter.py     # TextInserter: clipboard + synthetic Ctrl+V
├── hotkey_listener.py   # HotkeyListener: keyboard module hooks
└── settings_dialog.py   # SettingsDialog: PyQt5 modal dialog
```

### 7.1 Dependency Graph

```
main.py
 ├── config_manager.py
 ├── audio_recorder.py
 ├── transcription_service.py
 ├── text_inserter.py
 ├── hotkey_listener.py
 └── settings_dialog.py
      └── transcription_service.py
```

### 7.3 Threading Model

- **Main thread:** Qt event loop, tray UI, hotkey callbacks (via `QTimer.singleShot`).
- **Recording thread:** `threading.Thread` daemon inside `AudioRecorder._record()`.
- **Transcription thread:** `TranscriptionThread(QThread)` for each transcription request.

---

## 8. UI/UX Specification

### 8.1 Tray Icon

- **Visual:** Blue circle (`#1C59AA`), white "W", subtle dark border (`#144178`).
- **Size:** 64×64 px, rendered via `QPainter`.
- **Tooltip:** "WhisperApp".

### 8.2 Tray Menu

```
Status: Ready           [disabled]
─────────────────────────
Settings
About
─────────────────────────
Quit
```

Status values: `Ready`, `Recording...`, `Transcribing...`, `Ready (Hotkey Error)`.

### 8.3 Settings Dialog

```
┌────────────────────────────────────────┐
│ WhisperApp Settings              [_][X]│
├────────────────────────────────────────┤
│ OpenAI API Key    [sk-...        ****] │
│ Model             [whisper-1    ▼]     │
│ Language          [English      ▼]     │
│ Hotkey            [ctrl+shift+space]   │
│           Hotkey customization soon.   │
│ [✓] Automatically copy to clipboard    │
│ [✓] Show notifications                 │
├────────────────────────────────────────┤
│ [Test API Key]        [Save] [Cancel]  │
└────────────────────────────────────────┘
```

### 8.4 Dialog Flows

**Welcome (first run):**
```
┌────────────────────────────────────────┐
│ Welcome to WhisperApp              [X] │
├────────────────────────────────────────┤
│ Open Settings from the tray icon and   │
│ add your OpenAI API key.               │
│                              [   OK   ]│
└────────────────────────────────────────┘
```

**About:**
```
┌────────────────────────────────────────┐
│ About WhisperApp                   [X] │
├────────────────────────────────────────┤
│ WhisperApp                             │
│                                        │
│ Push-to-talk transcription from the    │
│ system tray.                           │
│                              [   OK   ]│
└────────────────────────────────────────┘
```

**Hotkey Error:**
```
┌────────────────────────────────────────┐
│ WhisperApp Hotkey Error            [X] │
├────────────────────────────────────────┤
│ Global hotkey could not be initialized.│
│                                        │
│ <exception text>                       │
│                                        │
│ Try running as Administrator.          │
│                              [   OK   ]│
└────────────────────────────────────────┘
```

---

## 9. API Integration

### 9.1 OpenAI Whisper Transcription

**Endpoint:** `POST https://api.openai.com/v1/audio/transcriptions`  
**SDK:** `openai>=1.58.0`

```python
client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file_handle,
    language="en",  # optional, omitted if ""
)
```

**Timeout:** 60 seconds via `httpx.Client(timeout=60.0)`.

### 9.2 API Key Validation

```python
client.models.list()
```

Any successful response confirms the key is valid.

---

## 10. Build & Distribution

### 10.1 PyInstaller Spec

A `WhisperApp.spec` shall be maintained in the repo root with:
- `--onefile --windowed`
- Hidden imports for:
  - `keyboard._winkeyboard`
  - `pyaudio._portaudio`
  - `cryptography.hazmat.bindings._rust`
  - `certifi`
- `upx=True` (optional — disable if AV false positives occur)
- Console disabled (`console=False`)

### 10.2 Build Script

A `build.bat` or `build.ps1` shall:
1. Activate the virtual environment.
2. Run `pyinstaller WhisperApp.spec`.
3. Output `dist/WhisperApp.exe`.

### 10.3 Versioning

- Source version tracked in `whisperapp/__init__.py` as `__version__`.
- The spec shall embed `VS_VERSIONINFO` with matching version strings.

---

## 11. Known Limitations & Product Debt

| ID | Limitation | Impact | Planned Resolution |
|----|-----------|--------|-------------------|
| L-1 | Hotkey customization UI exists but is not wired to runtime. | Users cannot change the shortcut. | v1.1 — Parse hotkey string and register dynamically. |
| L-2 | `audio_device` config field is unused. | Cannot select non-default microphone. | v1.1 — Populate from PyAudio device list. |
| L-3 | Clipboard is always overwritten on insertion. | Destroys prior clipboard contents. | v1.2 — Investigate `SendInput` direct text injection as alternative. |
| L-4 | `show_notifications` only gates success toast. | Cannot silence all notifications. | v1.1 — Apply setting to all non-error notifications. |
| L-5 | Single temp filename reused. | No concurrent recording; crash leaves last audio on disk. | v1.1 — Use UUID temp filenames + cleanup. |
| L-6 | Only `whisper-1` model exposed. | Cannot use newer OpenAI speech models. | v1.2 — Add `gpt-4o-transcribe` and `gpt-4o-mini-transcribe` options. |
| L-7 | No offline/local transcription. | Requires internet and API credits. | Future — Evaluate `faster-whisper` or `whisper.cpp` integration. |
| L-8 | Text insertion depends on focus stability. | May paste into wrong window. | Documented limitation; no planned fix. |

---

## 12. Open Questions

1. Should the app support multiple API key profiles (e.g., personal vs. work)?
2. Should there be a usage counter or cost estimator displayed in Settings?
3. Should the app support push-to-talk via mouse middle-click (as seen in original binary config)?
4. Should there be an auto-updater mechanism?
5. Should the app support proxy configuration for corporate networks?

---

## 13. Changelog

| Version | Date | Changes |
|---------|------|---------|
| 0.1.0 | 2025-12 | Initial source rebuild from reverse-engineered binary. |
| 1.0.0 | TBD | First production release with build pipeline, PRD, and resolved gaps. |
