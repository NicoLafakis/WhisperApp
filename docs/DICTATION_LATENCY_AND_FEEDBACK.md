# Dictation latency and feedback remediation

**Status:** Capture and queue work retained. The 2026-09-25 rollback restored the mic-responsive waveform and file transcription; physical hotkey and microphone behavior needs a user-session check.
**Scope:** Push-to-talk startup/save latency, recording feedback, transcription progress, and clipboard recovery.

## Findings

- Hotkey handlers called `AudioRecorder.start_recording()` and `stop_recording()` on the Qt UI thread. Startup performed retention cleanup, WAV setup, journal persistence, and PortAudio device open before the indicator appeared.
- The meter was refreshed only after WAV writing, flush, and `fsync`, so slow storage could leave a moving recording session with a flat indicator. The earlier visual was a multisine waveform; its replacement misread the requested KITT voice module as a left-to-right scanner.
- The app waited for the whole transcription response before showing more than a generic status. If a successful result could not be pasted because focus had changed, the old clipboard value remained while the new result was only available in History.
- A transcription failure correctly retained the WAV rather than putting audio bytes into a text clipboard. The UI did not state plainly that the clipboard had not changed.
- The follow-up report exposed two remaining visual defects: the scanner did not look like KITT's voice-responsive interior display, and the overlay hid immediately after stopping capture and at the start of each transcription result, leaving long uploads and retries looking idle.

## Remediation

1. Run audio startup and finalization in a retained `QThread`; show `STARTING` immediately and safely honor a hotkey release that arrives during startup.
2. Start capture before scheduling retention cleanup. Update the meter as soon as each audio chunk arrives, before disk flush and sync.
3. Use the earlier red waveform. Its amplitude and movement follow microphone level while recording; opening, saving, processing, queued, and retrying retain status text and elapsed time without simulated mic movement.
4. Use OpenAI's streamed file-transcription events for the default GPT Transcribe model and show accumulated partial text in the indicator. Keep `whisper-1` on its supported non-streaming request. Never insert preview text into the target app; paste only the final transcript.
5. If the final transcript cannot be pasted because focus changed, copy the current successful result when automatic copy is enabled. On failure, preserve the existing clipboard and tell the user that audio remains in Dictation History and the clipboard is unchanged.
6. Keep the overlay visible from hotkey press through save and transcription, including automatic retry waits. Show a brief final result after insertion or failure. Cancel any scheduled hide when a new recording or job begins.

## Behavior and limits

The indicator is immediate, but actual microphone activation still depends on Windows, the selected device, and its driver. This change removes UI blocking and avoidable file-history work from the front of capture; it does not keep the microphone open between hotkey presses. Partial text appears after the completed WAV has been uploaded and GPT Transcribe begins returning events. Text while the user is still speaking is possible with [Realtime transcription](https://developers.openai.com/api/docs/guides/realtime-transcription), which would require a separate streaming audio and text insertion design.

## Verification

- Focused tests cover worker-thread startup, immediate UI feedback, release during startup, waveform response to microphone level, continuous display through save and retry, streamed text deltas, legacy model fallback, and clipboard replacement after focus changes.
- The 2026-09-25 rollback suite passed: **140 passed**. The PyInstaller build and Inno Setup installer completed; uninstall and reinstall preserved settings and 59 WAV recordings. The installed executable matched the rebuilt package by SHA-256 and launched with the saved `Ctrl+Alt+Space` shortcut.
- The waveform was rendered offscreen for visual review. Processing shows a status label and elapsed time while the waveform stops moving.
- Supervisor re-review passed. The corrected PyInstaller build and Inno Setup installer compiled successfully. The previous app uninstalled successfully; the new installer exited 0, and the relaunched installed executable matched the packaged binary by SHA-256. Settings and recording-history folders remained present.
- For the five-column follow-up, the focused rendering test failed before the change and passed afterward. The full suite remained at **128 passed, 1 skipped**. PyInstaller and Inno Setup compiled successfully; the previous app uninstalled, the new installer exited 0, and the relaunched installed executable matched the packaged binary by SHA-256.
- Physical microphone activation and a live OpenAI transcription were not exercised in this unattended pass. The earlier local PortAudio diagnostic could not open the microphone device, so the device-dependent latency and captured-audio path still need a real user dictation to verify.

## 2026-09-23 hotkey and short-dictation regression

- The keyboard hook's cached modifier state could be stale after a missed key-up. A later space press could then be mistaken for `Ctrl+Shift+Space`. The hotkey listener now cross-checks held modifiers against Windows `GetAsyncKeyState` before starting capture and logs accepted presses and releases. Configured custom chord keys use Windows scan-code mapping for the same check. The primary key is excluded because Windows updates its asynchronous state after the low-level hook callback.
- A due retry from an older failed upload was selected before a new pending dictation. Fresh pending recordings now take priority, while older retries remain durable. Background retries do not start during a new recording. If a retry is already in flight, the new recording gets a separate foreground transcription worker and can complete without waiting for that retry. A late older result remains in History and cannot overwrite the newer clipboard or Last Transcription action.
- The five-column widget rendered at approximately **0.45 ms per frame** in an offscreen 1,000-frame local measurement. It is not on the network or transcription worker path. The live log showed repeated `WinError 10054` connection resets, and a separate unauthenticated TLS check also reset intermittently. A 0.25-second local probe with the configured API key completed in **1.33 s without streaming** and **0.66 s with streaming**; this single probe does not establish typical latency.
- Regression tests first failed for stale modifier state, retry ordering, an in-flight retry blocking a new take, custom chord verification, and a late retry replacing the clipboard; each passed after its fix. The installed microphone and real hotkey behavior still require a user-session check.
- The independent supervisor re-review passed: **47 focused tests passed** and the full suite finished at **135 passed, 1 skipped**. PyInstaller and Inno Setup rebuilt successfully. The previous installation was removed, the new installer exited 0, and the relaunched installed executable matched the packaged executable by SHA-256. Settings and recording-history folders remained present.
