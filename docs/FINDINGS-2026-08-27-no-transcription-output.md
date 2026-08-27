# Finding: No transcription output (2026-08-27)

**Status:** Root cause confirmed. Remediation in progress.
**Reported:** App starts, key validates, settings open, waveform reacts to voice — but releasing PTT produces no text and nothing on the clipboard.

---

## Root cause

The OpenAI account has **no credits remaining**. Every `POST /v1/audio/transcriptions`
returns HTTP 429 with:

```json
{
  "error": {
    "message": "You have no credits remaining. Add credits to continue using the API at https://platform.openai.com/settings/organization/billing/.",
    "type": "insufficient_quota",
    "code": "credit_balance_exhausted"
  }
}
```

Verified 2026-08-27 by replaying a captured WAV from `%TEMP%\whisperapp\` against the
live endpoint with the app's own stored key. The audio pipeline is healthy — the WAVs
on disk are well-formed and non-silent. Nothing in the recording path is broken.

`%TEMP%\whisperapp\runtime.log` shows this 429 on every transcription attempt going
back to at least 11:04 on 2026-08-27, each one retried three times by the OpenAI SDK
and then abandoned.

**Fix (account-side, not code):** add credits at
<https://platform.openai.com/settings/organization/billing/>.

---

## Why this presented as silence — the real defects

The account state is Nico's to fix. The reason it cost a morning of confusion is ours.
Four defects turned a clear, well-labelled API error into a no-op.

### D1 — Failures are invisible and the status lies

`WhisperTrayApp._on_transcription_finished` reports errors *only* through
`self.notify(...)`, a transient Windows tray balloon that Focus Assist, notification
settings, or a glance away will swallow. Immediately before that it calls
`set_status("Ready")`, so the tray menu reads **Ready** after a total failure —
indistinguishable from success. There is no persistent failure surface anywhere in the
UI, and the log that *does* hold the answer is buried in `%TEMP%`.

### D2 — "Test API Key" validates the wrong capability

`TranscriptionService.test_api_key` calls `client.models.list()`. That endpoint is not
quota-gated: it returns 200 OK on a key with a zero credit balance. So the Settings
dialog cheerfully reports **"API key is valid"** for a key that cannot transcribe a
single second of audio. This is precisely the false signal that sent the investigation
away from billing. Confirmed in the log at 12:58:01 — `GET /v1/models` 200 OK,
followed 22 seconds later by `POST /v1/audio/transcriptions` 429.

### D3 — Runaway recording with no duration or size guard

`%TEMP%\whisperapp\recording_6bf9cdc9....wav` is **160,272,428 bytes** — roughly 83
minutes at 16 kHz mono 16-bit. Push-to-talk got stuck (release never fired) and the
recorder ran unbounded. There is no maximum-duration cap in `AudioRecorder`, and no
size check before upload. OpenAI's transcription file limit is 25 MB, so any recording
past ~13 minutes is a guaranteed failure that still burns a full upload first.

### D4 — Hotkey unhook raises `KeyError` on every teardown

`HotkeyListener.start` registers both `on_press_key` and `on_release_key` against the
same primary key. The `keyboard` library stores these under one shared entry, so the
first `unhook` removes it and the second raises `KeyError: 'space'`. The log is full of
these. Related: **two `WhisperApp.exe` instances were running concurrently** during the
session (double "WhisperApp started" entries at 12:05:10 and 12:05:15) — there is no
single-instance guard, so hotkeys get double-registered across processes.

---

## Remediation

| # | Fix | Surface |
|---|---|---|
| D1 | Classify API errors and surface them persistently — tray status holds the failure, quota errors get an actionable dialog naming the billing page | `main.py`, `transcription_service.py` |
| D2 | Make "Test API Key" exercise the real transcription capability so quota exhaustion fails the test | `transcription_service.py`, `settings_dialog.py` |
| D3 | Cap recording duration, auto-stop at the cap, and reject oversized files before upload with a clear message | `audio_recorder.py`, `main.py` |
| D4 | Unhook defensively; add a single-instance guard | `hotkey_listener.py`, `main.py` |

Regression tests cover the error classification, the capability check, and the size
guard. The repo had no test suite before this finding.
