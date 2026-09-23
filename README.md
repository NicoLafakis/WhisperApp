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

The hotkey still records while held, then transcribes and pastes on release. Startup
and save work runs off the UI thread; the on-screen Knight Rider scanner immediately
shows whether the microphone is opening, recording, saving, or transcribing. For the
default GPT Transcribe model, the overlay also shows partial text while OpenAI processes
the completed recording. Partial text is only a preview; only the final result is
inserted. `whisper-1` uses its normal non-streaming response. If automatic paste is
skipped because focus changed, a completed result is copied to the clipboard when
automatic copy is enabled. Failed transcription leaves the clipboard untouched and
clearly reports that the audio is saved in Dictation History.

The language selector supplies the plural `languages` hint required by GPT Transcribe;
Auto Detect omits the hint. File transcription can stream partial text after the audio
has been recorded and uploaded. Live transcription while the microphone is still
capturing requires the separate Realtime API path. See [OpenAI file transcription](https://developers.openai.com/api/docs/guides/speech-to-text).

Run regression checks with `python -m pytest -q`.

## Build & Packaging

Build an unsigned development copy:

```powershell
.\build.ps1 -Clean -SkipInstall
```

Run `dist\WhisperApp\WhisperApp.exe`. The build is labeled as an unsigned development artifact.

Build and verify a signed release candidate (requires Inno Setup, SignTool, and a publicly trusted RSA signing identity):

```powershell
.\build.ps1 -Release -SkipInstall -Installer -Sign -Thumbprint YOUR_PUBLICLY_TRUSTED_CERTIFICATE_THUMBPRINT
```

Release mode signs and verifies each shipped native PE binary, the installer, the generated uninstaller, and all installed native files. It cleans prior outputs and fails closed if required tools, credentials, timestamps, signatures, or fresh artifacts are missing. It packages an onedir build so native files can be inspected individually. Signing does not guarantee antivirus or Smart App Control acceptance. See [Windows release signing guide](docs/WINDOWS_SECURITY_AND_ANTIVIRUS.md) for the Windows manual checklist and signing details.

Quit any running tray instance before launching the new executable; the single-instance guard prevents two copies running.

The Windows voice-command proposal is in [Jarvis proposal](docs/JARVIS_PROPOSAL.md).
