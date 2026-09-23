# Dictation latency and feedback remediation

**Status:** Implemented, supervisor reviewed, built, reinstalled, and restarted
**Scope:** Push-to-talk startup/save latency, recording feedback, transcription progress, and clipboard recovery.

## Findings

- Hotkey handlers called `AudioRecorder.start_recording()` and `stop_recording()` on the Qt UI thread. Startup performed retention cleanup, WAV setup, journal persistence, and PortAudio device open before the indicator appeared.
- The meter was refreshed only after WAV writing, flush, and `fsync`, so slow storage could leave a moving recording session with a flat indicator. The visual itself was a multisine waveform and stopped moving below its fixed noise threshold.
- The app waited for the whole transcription response before showing more than a generic status. If a successful result could not be pasted because focus had changed, the old clipboard value remained while the new result was only available in History.
- A transcription failure correctly retained the WAV rather than putting audio bytes into a text clipboard. The UI did not state plainly that the clipboard had not changed.

## Remediation

1. Run audio startup and finalization in a retained `QThread`; show `STARTING` immediately and safely honor a hotkey release that arrives during startup.
2. Start capture before scheduling retention cleanup. Update the meter as soon as each audio chunk arrives, before disk flush and sync.
3. Replace the multisine drawing with a continuously sweeping red Knight Rider scanner. Show `STARTING`, `RECORDING`, `SAVING`, and `TRANSCRIBING`, and use real input level for scanner glow. Continue scanner motion in silence.
4. Use OpenAI's streamed file-transcription events for the default GPT Transcribe model and show accumulated partial text in the indicator. Keep `whisper-1` on its supported non-streaming request. Never insert preview text into the target app; paste only the final transcript.
5. If the final transcript cannot be pasted because focus changed, copy the current successful result when automatic copy is enabled. On failure, preserve the existing clipboard and tell the user that audio remains in Dictation History and the clipboard is unchanged.

## Behavior and limits

The indicator is immediate, but actual microphone activation still depends on Windows, the selected device, and its driver. This change removes UI blocking and avoidable file-history work from the front of capture; it does not keep the microphone open between hotkey presses. Partial text appears after the completed WAV has been uploaded and GPT Transcribe begins returning events. Text that appears while the user is still speaking requires the Realtime transcription API and is outside this change.

## Verification

- Focused tests cover worker-thread startup, immediate UI feedback, release during startup, scanner motion in silence, meter update before a blocked disk sync, streamed text deltas, legacy model fallback, and clipboard replacement after focus changes.
- Full suite: **123 passed, 1 skipped**. The skipped release-verifier test requires `Microsoft.PowerShell.Security`, which this host failed to load; the other release certificate and signer tests ran.
- PyInstaller onedir build completed with Python 3.12.14 and PyInstaller 6.22.0; Inno Setup 6.7.3 produced `installer/WhisperApp-Setup-1.1.0.exe` (unsigned development build).
- Uninstalled the prior copy, installed this package, and launched the installed executable. The new process remained running; the settings directory and 79 recording-store files were present after installation.
- The reviewer signed off after checking that the PRD matches the existing concurrent-upload behavior and clipboard fallback. `git diff --check` passed.
- Physical microphone activation and a live OpenAI transcription were not exercised in this unattended pass. The earlier local PortAudio diagnostic could not open the microphone device, so the device-dependent latency and captured-audio path still need a real user dictation to verify.
