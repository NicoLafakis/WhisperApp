# WhisperApp (Source Rebuild)

This repository now contains a source-based rebuild of the reverse-engineered WhisperApp behavior documented in `docs/REVERSE_ENGINEERED_PRD.md`.

## Current scope

Implemented baseline behavior:
- System tray app with status, Settings, About, Quit
- Startup notification and missing-key onboarding prompt
- Settings persisted to `%USERPROFILE%\\.whisperapp`
- API key encrypted with Fernet in `config.json`
- Push-to-talk recording on `Ctrl+Shift+Space` (space press/release with ctrl+shift held)
- WAV recording to `%TEMP%\\whisperapp\\recording.wav`
- OpenAI transcription via `client.audio.transcriptions.create(...)`
- Clipboard + synthetic `Ctrl+V` insertion flow
- Notification behavior aligned with recovered app

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
python -m whisperapp
```

## Notes

- Platform target is Windows.
- `keyboard` global hooks may require elevated permissions depending on local policy.
- `PyAudio` may require system audio drivers or wheels depending on Python version.
