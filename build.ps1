# WhisperApp Build Script
# Requires: Python 3.11+, pip, virtual environment (recommended), Inno Setup 6 (optional for installer)
# Usage: .\build.ps1 [-Clean] [-SkipInstall] [-Installer] [-Sign]

param(
    [switch]$Clean,
    [switch]$SkipInstall,
    [switch]$Installer,
    [switch]$Sign,
    [string]$Thumbprint,
    [string]$PfxPath,
    [string]$PfxPassword
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

# Resolve Python & PyInstaller
$python = if (Test-Path ".\.venv\Scripts\python.exe") { ".\.venv\Scripts\python.exe" } else { "python" }
$pyinstaller = if (Test-Path ".\.venv\Scripts\pyinstaller.exe") { ".\.venv\Scripts\pyinstaller.exe" } else { "pyinstaller" }

# Ensure dependencies are installed
if (-not $SkipInstall) {
    Write-Header "Installing dependencies"
    & $python -m pip install -r requirements.txt
    & $python -m pip install pyinstaller
}

# Build the executable
Write-Header "Building $AppName.exe (PyInstaller, upx=False, Windows Manifest)"
& $pyinstaller WhisperApp.spec --clean

# Verify output
$exePath = "dist\$AppName.exe"
if (Test-Path $exePath) {
    $size = (Get-Item $exePath).Length
    Write-Header "Executable build successful"
    Write-Host "Output: $exePath" -ForegroundColor Green
    Write-Host "Size: $([math]::Round($size / 1MB, 2)) MB" -ForegroundColor Green
} else {
    Write-Error "Build failed: $exePath not found"
    exit 1
}

# Sign executable if requested
if ($Sign) {
    Write-Header "Digitally signing $AppName.exe"
    $signScript = Join-Path $PSScriptRoot "scripts\Sign-Binary.ps1"
    $signParams = @{ FilePath = $exePath }
    if ($Thumbprint) { $signParams["Thumbprint"] = $Thumbprint }
    if ($PfxPath) { $signParams["PfxPath"] = $PfxPath }
    if ($PfxPassword) { $signParams["PfxPassword"] = $PfxPassword }
    & $signScript @signParams
}

# Build installer if requested
if ($Installer) {
    Write-Header "Building Inno Setup Installer"

    $iscc = $null
    $isccCandidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\iscc.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\iscc.exe",
        "${env:ProgramFiles}\Inno Setup 6\iscc.exe"
    )
    foreach ($cand in $isccCandidates) {
        if (Test-Path $cand) {
            $iscc = $cand
            break
        }
    }
    if (-not $iscc) {
        $cmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
        if ($cmd) { $iscc = $cmd.Source }
    }

    if (-not $iscc) {
        Write-Warning "Inno Setup compiler (iscc.exe) not found. Skipping installer creation."
    } else {
        Write-Host "Using Inno Setup compiler: $iscc" -ForegroundColor Cyan
        & $iscc installer.iss
        if ($LASTEXITCODE -ne 0) {
            Write-Error "Inno Setup compiler failed with exit code $LASTEXITCODE"
            exit 1
        }

        # Locate generated installer
        $installerFiles = Get-ChildItem "installer\WhisperApp-Setup-*.exe" | Sort-Object LastWriteTime -Descending
        if ($installerFiles) {
            $latestInstaller = $installerFiles[0].FullName
            Write-Host "Installer created: $latestInstaller" -ForegroundColor Green

            if ($Sign) {
                Write-Header "Digitally signing installer"
                $signScript = Join-Path $PSScriptRoot "scripts\Sign-Binary.ps1"
                $signParams = @{ FilePath = $latestInstaller }
                if ($Thumbprint) { $signParams["Thumbprint"] = $Thumbprint }
                if ($PfxPath) { $signParams["PfxPath"] = $PfxPath }
                if ($PfxPassword) { $signParams["PfxPassword"] = $PfxPassword }
                & $signScript @signParams
            }
        }
    }
}

Write-Host "`nDone. Run with: .\dist\$AppName.exe" -ForegroundColor Cyan
