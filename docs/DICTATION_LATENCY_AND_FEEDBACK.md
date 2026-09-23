# Dictation latency and feedback remediation

**Status:** Follow-up correction packaged, supervisor-reviewed, installed, and running
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
3. Use three vertical red LED columns modeled on KITT's voice module. Their lit segments follow the actual microphone level while recording; opening, saving, processing, queued, and retrying have a separate animation and elapsed timer.
4. Use OpenAI's streamed file-transcription events for the default GPT Transcribe model and show accumulated partial text in the indicator. Keep `whisper-1` on its supported non-streaming request. Never insert preview text into the target app; paste only the final transcript.
5. If the final transcript cannot be pasted because focus changed, copy the current successful result when automatic copy is enabled. On failure, preserve the existing clipboard and tell the user that audio remains in Dictation History and the clipboard is unchanged.
6. Keep the overlay visible from hotkey press through save and transcription, including automatic retry waits. Show a brief final result after insertion or failure. Cancel any scheduled hide when a new recording or job begins.

## Behavior and limits

The indicator is immediate, but actual microphone activation still depends on Windows, the selected device, and its driver. This change removes UI blocking and avoidable file-history work from the front of capture; it does not keep the microphone open between hotkey presses. Partial text appears after the completed WAV has been uploaded and GPT Transcribe begins returning events. Text while the user is still speaking is possible with [Realtime transcription](https://developers.openai.com/api/docs/guides/realtime-transcription), which would require a separate streaming audio and text insertion design.

## Verification

- Focused tests cover worker-thread startup, immediate UI feedback, release during startup, voice LED response to microphone level, processing animation, continuous display through save and retry, streamed text deltas, legacy model fallback, and clipboard replacement after focus changes. Current focused result: **18 passed**.
- Current full suite: **128 passed, 1 skipped**. The skip is the release-verifier test that requires `Microsoft.PowerShell.Security`, which this PowerShell host could not load.
- Rendered the recording and processing states offscreen for visual review. The recording state shows three red LED columns; the processing state shows a distinct status label, elapsed time, and animated columns.
- Supervisor re-review passed. The corrected PyInstaller build and Inno Setup installer compiled successfully. The previous app uninstalled successfully; the new installer exited 0, and the relaunched installed executable matched the packaged binary by SHA-256. Settings and recording-history folders remained present.
- Physical microphone activation and a live OpenAI transcription were not exercised in this unattended pass. The earlier local PortAudio diagnostic could not open the microphone device, so the device-dependent latency and captured-audio path still need a real user dictation to verify.
