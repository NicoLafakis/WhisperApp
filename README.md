# WhisperApp (Source Rebuild)

This repository now contains a source-based rebuild of the reverse-engineered WhisperApp behavior documented in `docs/REVERSE_ENGINEERED_PRD.md`.

## Current scope

Implemented baseline behavior:
- System tray app with status, Settings, About, Quit
- Startup notification and missing-key onboarding prompt
- Settings persisted to `%USERPROFILE%\\.whisperapp`
- API key encrypted with Fernet in `config.json`
- Push-to-talk recording on `Ctrl+Shift+Space` (space press/release with ctrl+shift held)
- WAV recording to `<Documents>\\WhisperApp\\recordings\\recording_<id>.wav` (last 25 kept)
- GPT Transcribe dictation via `client.audio.transcriptions.create(...)`
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

## Transcription upgrade (September 2026)

New installations use `gpt-transcribe`. On first launch after upgrading, existing
`whisper-1` settings migrate automatically while preserving the encrypted key and
preferences. Settings offers `whisper-1` as a temporary manual fallback; that choice
survives subsequent launches. Test API Key checks the selected model.

The hotkey still records while held, then transcribes and pastes on release. The
language selector now supplies the plural `languages` hint required by GPT Transcribe;
Auto Detect omits the hint. This release does not add streaming or spoken responses.
See [OpenAI file transcription](https://developers.openai.com/api/docs/guides/speech-to-text).

Run regression checks with `python -m pytest -q`.

## Build & Packaging

Build the executable and digitally signed Inno Setup installer:

```powershell
.\build.ps1 -Clean -SkipInstall -Installer -Sign
```

This builds `dist/WhisperApp.exe`, compiles `installer/WhisperApp-Setup-1.1.0.exe`, and signs both with Authenticode SHA256 and RFC 3161 timestamps to satisfy Windows security standards and prevent antivirus (McAfee, Defender) false positives. See [Windows Security & Antivirus Guide](docs/WINDOWS_SECURITY_AND_ANTIVIRUS.md) for certificate configuration, trust setup, and false positive procedures.

Quit any running tray instance before launching the new `dist/WhisperApp.exe`; the single-instance guard prevents two copies running.

The Windows voice-command proposal is in [Jarvis proposal](docs/JARVIS_PROPOSAL.md).

