# Intermittent dictation repair — September 22, 2026

The product contract remains hold-to-record, release-to-transcribe, and automatic
clipboard paste into the focused application. See `PRD.md`, sections 1, 3, and 4;
the model and recording-storage updates in `README.md` supersede the original
model and single temporary-file details. Jarvis is a separate application.

## Observed evidence

The installed September 13 executable logged a microphone-open error (`-9999`),
repeated connection errors, and empty transcription results. The latest stored
recordings contain PCM frames. Fresh source-runtime checks captured microphone
frames and successfully transcribed synthetic speech twice using the configured
model and saved key. The historical network failures were not reproduced; their
underlying transport cause was not logged by the previous implementation.

## Repairs

- Dispatch keyboard callbacks using explicitly queued Qt signals.
- Refresh PortAudio and retry once when opening the microphone fails.
- Notify the controller when audio capture fails, ending the take and transcribing
  any captured frames instead of leaving the recording indicator active.
- Recover controller state if saving a recording raises an error.
- Distinguish connection failures and retain their exception chain in the log.
- Provide **Retry Last Recording** for the most recent transcription attempt in
  the current session; retry is disabled while recording or transcribing.
- Retry temporary clipboard contention and wait briefly for held modifiers to
  release before sending Ctrl+V. If they remain held, retain text for manual copy.
- Retain successful text in memory and provide **Copy Last Transcription**, even
  if automatic insertion raises an exception. Normal success still pastes text.
- Log capture start and saved frame counts without logging dictated text.

## Verification boundaries

Regression tests cover the threaded hotkey-to-output controller flow across three
consecutive takes, microphone recovery, capture failure, save failure, network
classification, retry, and clipboard failures. Real microphone and API checks
are separate from the mocked automated suite. Paste into arbitrary third-party
applications remains best-effort, as specified in FR-5.3; focus changes and Windows
privilege boundaries cannot be detected merely by sending Ctrl+V.
