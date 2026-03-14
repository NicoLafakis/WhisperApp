$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$buildLog = Join-Path $root "build.log"
"==== $(Get-Date -Format s) Build start ====" | Out-File -FilePath $buildLog -Append -Encoding utf8

function Find-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return "py"
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return "python"
    }
    throw "Python was not found. Install Python 3 and ensure 'py' or 'python' is in PATH."
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command
    )

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        & $Command 2>&1 | Tee-Object -FilePath $buildLog -Append | Out-Host
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

try {
    $venvPath = Join-Path $root ".venv"
    $pythonExe = Join-Path $venvPath "Scripts\python.exe"

    if (-not (Test-Path $pythonExe)) {
        $bootstrap = Find-PythonCommand
        Write-Host "Creating virtual environment..."
        if ($bootstrap -eq "py") {
            $code = Invoke-LoggedCommand { py -3 -m venv .venv }
        }
        else {
            $code = Invoke-LoggedCommand { python -m venv .venv }
        }

        if ($code -ne 0) {
            throw "Failed to create .venv. See build.log"
        }
    }

    $pythonExe = Join-Path $venvPath "Scripts\python.exe"
    $pipExe = Join-Path $venvPath "Scripts\pip.exe"

    Write-Host "Installing app dependencies..."
    $code = Invoke-LoggedCommand { & $pipExe install -r requirements.txt --disable-pip-version-check }
    if ($code -ne 0) {
        throw "Dependency install failed. See build.log"
    }

    Write-Host "Installing PyInstaller..."
    $code = Invoke-LoggedCommand { & $pipExe install pyinstaller --disable-pip-version-check }
    if ($code -ne 0) {
        throw "PyInstaller install failed. See build.log"
    }

    Write-Host "Building WhisperApp.exe..."
    $pyInstallerArgs = @(
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--noconsole",
        "--name", "WhisperApp",
        "--collect-submodules", "PyQt5",
        "--hidden-import", "keyboard",
        "--hidden-import", "pyaudio",
        "--paths", ".",
        "run_whisperapp.py"
    )
    $code = Invoke-LoggedCommand { & $pythonExe @pyInstallerArgs }
    if ($code -ne 0) {
        throw "PyInstaller build failed. See build.log"
    }

    $candidateExePaths = @(
        (Join-Path $root "dist\WhisperApp.exe"),
        (Join-Path $root "dist\WhisperApp\WhisperApp.exe")
    )
    $builtExe = $candidateExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if (-not $builtExe) {
        throw "Build finished but no WhisperApp executable was found under dist\\."
    }

    Write-Host "Build complete: $builtExe"
}
catch {
    $_ | Out-String | Tee-Object -FilePath $buildLog -Append | Out-Host
    exit 1
}
finally {
    "==== $(Get-Date -Format s) Build end ====" | Out-File -FilePath $buildLog -Append -Encoding utf8
}
