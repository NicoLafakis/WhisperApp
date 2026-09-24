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
- Realtime transcription while recording, with finalized phrases typed into the focused app
- Durable WAV capture and file-transcription recovery if the live connection fails
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

The hotkey starts microphone capture and Realtime transcription together. Finalized
speech phrases are typed into the app that was focused when recording began; a brief
pause commits a phrase while recording continues. If focus changes, WhisperApp stops
typing into other windows and keeps the transcript in Dictation History. A compact
recording meter opens near the top-right of the active screen, can be dragged, and
remembers its position. Automatic copy places the completed transcript on the clipboard
when enabled.

The app continues saving the WAV and journal during live transcription. If Realtime is
unavailable or fails before any text was typed, the saved WAV uses the normal file
transcription and insertion path. If some live phrases were already typed, fallback
transcription updates Dictation History and the clipboard (when enabled) without typing
the same dictation a second time. Settings still offer `gpt-transcribe` and `whisper-1`
for file transcription and recovery.

The language selector supplies the plural `languages` hint to Realtime transcription;
Auto Detect omits the hint. See [OpenAI Realtime transcription](https://developers.openai.com/api/docs/guides/realtime-transcription)
and [OpenAI file transcription](https://developers.openai.com/api/docs/guides/speech-to-text).

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
