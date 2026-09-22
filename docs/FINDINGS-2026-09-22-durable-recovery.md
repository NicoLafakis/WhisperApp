# Durable dictation recovery

## Confirmed failure

The September 22 09:46:53 recording was saved with 956,416 PCM frames (59.776
seconds). At 09:46:54 the upload failed during TLS setup with `WinError 10054`:
the connection was forcibly closed. The app restarted at 09:47:17. Audio survived,
but the previous repair kept its retry pointer and completed text only in memory.
The failed recording was subsequently transcribed successfully and both its audio
and recovered text were preserved under `Documents/WhisperApp/recovered`.

The evidence establishes a transport reset, not which network intermediary caused
it. A connection reset must not require the user to reconstruct their dictation.

## Product requirements amendment

The core product remains the tray-only hold-to-record, release-to-transcribe,
automatic-paste utility described in `PRD.md`. The following requirements supersede
the older single-worker rejection, memory-only output, and unconditional audio
retention rules:

- Write PCM audio and update its WAV header during capture; flush and fsync each
  chunk. On restart, repair interrupted header lengths and recover the saved take.
- Maintain an atomic per-recording journal. Pending, interrupted, and temporarily
  failed uploads survive restarts. A corrupt journal leaves the audio visible for
  manual recovery rather than deleting it or guessing that it succeeded.
- Retry connection errors, rate limits, and server errors automatically, with
  exponential backoff capped at 60 seconds. Authentication, billing, empty output,
  and invalid-request failures remain visible for explicit recovery.
- Accept new recordings while older uploads are running or awaiting retry.
- Save completed text to a durable text file before notifying the UI or attempting
  paste. Completed jobs are not retranscribed after restart.
- Never automatically delete unfinished or unclassified audio. The 25-take audio
  retention budget applies only to completed recordings; saved text remains.
- Offer Dictation History with the saved text, recording status, copy, retry, and
  access to the saved files. History survives restarts and completed-audio pruning.
- Automatically paste fresh text only while its original foreground window remains
  active and no newer recording has started. A same-session transient retry can
  still finish normal automatic paste. Restarted or superseded jobs remain in
  history and announce that text is ready, avoiding an unexpected paste elsewhere.
- On quit, finalize captured audio and allow an active worker to save its result
  before releasing the single-instance mutex.
- Preserve encrypted settings across uninstall/reinstall. The previous installer
  explicitly removed the configuration directory during uninstall.

## Fault verification

Automated checks exercise the real OpenAI SDK against a mock HTTP transport with
`WinError 10054` every thirtieth request, over 35 separate 90-second WAV files. All
35 texts are saved, with 36 total requests. No external API is called by that test.
Additional checks cover process termination during real WAV writes, incomplete
headers, restart recovery, retry timing, corrupt metadata, metadata-write failure
after text is saved, failed paste, changed focus, shutdown during transcription,
history display, and retention with more than 30 unfinished recordings.

The preceding live recovery also confirmed that the user's failed minute of audio
could be transcribed. These checks demonstrate recovery from the tested failures;
they do not imply control over network availability, disk hardware, or whether a
third-party application accepts a synthetic paste.
