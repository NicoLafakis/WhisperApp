# WhisperApp Final Folder

This folder is set up so you can start quickly.

## Fast start

1. Double-click `Start-WhisperApp.bat`
2. WhisperApp launches to the system tray in the background
3. Open tray `Settings` and paste your OpenAI API key (first time only)
4. Use `Ctrl+Shift+Space`

`Start-WhisperApp.bat` auto-closes immediately.

## Build a real EXE

Run:

- `Build-WhisperApp-Exe.bat`

This creates a PyInstaller build at one of:
- `dist\\WhisperApp.exe` (one-file mode)
- `dist\\WhisperApp\\WhisperApp.exe` (one-folder mode)

After build, `Start-WhisperApp.bat` automatically prefers the built EXE.

## If startup fails

- Check `startup.log` in this folder
- Check `%TEMP%\\whisperapp\\runtime.log`
- Optional: run `Start-WhisperApp-Debug.bat` to see launcher output in a console

## Troubleshooting build

- Check `build.log` in this folder for PyInstaller output.

## Manual run

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m whisperapp
```
