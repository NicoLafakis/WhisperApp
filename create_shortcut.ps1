# Whisper App Desktop Shortcut Creator
# Run this once to create a desktop shortcut for easy access

$scriptPath = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonScript = Join-Path $scriptPath "whisper.py"
$batchFile = Join-Path $scriptPath "run_whisper_silent.bat"

# Check if Python is available
try {
    $pythonPath = (Get-Command python).Source
    Write-Host "Python found at: $pythonPath" -ForegroundColor Green
} catch {
    Write-Host "Python not found in PATH. Please install Python or add it to PATH." -ForegroundColor Red
    Read-Host "Press Enter to continue anyway..."
}

# Create desktop shortcut
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "Whisper STT.lnk"

$WshShell = New-Object -comObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($shortcutPath)
$Shortcut.TargetPath = $batchFile
$Shortcut.WorkingDirectory = $scriptPath
$Shortcut.IconLocation = "shell32.dll,23"  # Microphone icon
$Shortcut.Description = "Whisper Speech-to-Text App"
$Shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created: $shortcutPath" -ForegroundColor Green
Write-Host ""
Write-Host "Hotkeys:" -ForegroundColor Yellow
Write-Host "  Ctrl+0 : Record and transcribe speech" -ForegroundColor Cyan
Write-Host "  \      : Toggle Whisper on/off" -ForegroundColor Cyan
Write-Host ""
Write-Host "Double-click the desktop shortcut to start Whisper!" -ForegroundColor Green
Write-Host ""

# Optionally run the app now
$response = Read-Host "Do you want to start Whisper now? (y/n)"
if ($response -eq 'y' -or $response -eq 'Y') {
    Start-Process -FilePath $batchFile -WorkingDirectory $scriptPath
    Write-Host "Whisper started! Check the settings if needed." -ForegroundColor Green
}

Read-Host "Press Enter to exit"