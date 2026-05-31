# WhisperApp Build Script
# Requires: Python 3.11+, pip, virtual environment (recommended)
# Usage: .\build.ps1

param(
    [switch]$Clean,
    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$AppName = "WhisperApp"

function Write-Header($text) {
    Write-Host "`n=== $text ===" -ForegroundColor Cyan
}

# Clean previous builds
if ($Clean) {
    Write-Header "Cleaning previous builds"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "dist"
    Remove-Item -Recurse -Force -ErrorAction SilentlyContinue "build"
}

# Ensure dependencies are installed
if (-not $SkipInstall) {
    Write-Header "Installing dependencies"
    pip install -r requirements.txt
    pip install pyinstaller
}

# Build the executable
Write-Header "Building $AppName.exe"
pyinstaller WhisperApp.spec --clean

# Verify output
$exePath = "dist\$AppName.exe"
if (Test-Path $exePath) {
    $size = (Get-Item $exePath).Length
    Write-Header "Build successful"
    Write-Host "Output: $exePath" -ForegroundColor Green
    Write-Host "Size: $([math]::Round($size / 1MB, 2)) MB" -ForegroundColor Green
} else {
    Write-Error "Build failed: $exePath not found"
    exit 1
}

Write-Host "`nDone. Run with: .\dist\$AppName.exe" -ForegroundColor Cyan
