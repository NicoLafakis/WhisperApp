$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$startupLog = Join-Path $root "startup.log"
"==== $(Get-Date -Format s) Launcher start ====" | Out-File -FilePath $startupLog -Append -Encoding utf8

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
        & $Command 2>&1 | Tee-Object -FilePath $startupLog -Append | Out-Host
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previous
    }
}

try {
    $candidateExePaths = @(
        (Join-Path $root "dist\WhisperApp.exe"),
        (Join-Path $root "dist\WhisperApp\WhisperApp.exe")
    )
    $distExe = $candidateExePaths | Where-Object { Test-Path $_ } | Select-Object -First 1

    if ($distExe) {
        Write-Host "Starting built executable..."
        $exeDir = Split-Path -Parent $distExe
        $proc = Start-Process -FilePath $distExe -WorkingDirectory $exeDir -PassThru
        Start-Sleep -Milliseconds 1200

        if ($proc.HasExited) {
            $tempLog = Join-Path $env:TEMP "whisperapp\runtime.log"
            throw "WhisperApp.exe exited immediately. Check: $tempLog and startup.log"
        }

        Write-Host ("WhisperApp.exe started (PID {0})." -f $proc.Id)
        return
    }

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
            throw "Failed to create .venv. See startup.log in this folder."
        }
    }

    $pythonExe = Join-Path $venvPath "Scripts\python.exe"
    $pythonwExe = Join-Path $venvPath "Scripts\pythonw.exe"
    $pipExe = Join-Path $venvPath "Scripts\pip.exe"
    $depsMarker = Join-Path $venvPath ".deps_installed"
    $requirementsPath = Join-Path $root "requirements.txt"

    $needsInstall = $true
    if ((Test-Path $depsMarker) -and (Test-Path $requirementsPath)) {
        $markerTime = (Get-Item $depsMarker).LastWriteTimeUtc
        $reqTime = (Get-Item $requirementsPath).LastWriteTimeUtc
        if ($markerTime -ge $reqTime) {
            $needsInstall = $false
        }
    }

    if ($needsInstall) {
        Write-Host "Installing/updating dependencies..."
        $code = Invoke-LoggedCommand { & $pipExe install -r requirements.txt --disable-pip-version-check }
        if ($code -ne 0) {
            throw "Dependency install failed. See startup.log in this folder."
        }

        Set-Content -Path $depsMarker -Value (Get-Date -Format s) -Encoding ascii
    }
    else {
        Write-Host "Dependencies already installed."
    }

    # Quick preflight so launch failures are visible before detaching.
    $code = Invoke-LoggedCommand { & $pythonExe -c "import whisperapp.main" }
    if ($code -ne 0) {
        throw "Preflight import failed. See startup.log in this folder."
    }

    Write-Host ""
    Write-Host "Starting WhisperApp (python fallback)..."
    $launchExe = $pythonExe
    if (Test-Path $pythonwExe) {
        $launchExe = $pythonwExe
    }

    $proc = Start-Process -FilePath $launchExe -ArgumentList @("-m", "whisperapp") -WorkingDirectory $root -PassThru
    Start-Sleep -Milliseconds 1200

    if ($proc.HasExited) {
        $tempLog = Join-Path $env:TEMP "whisperapp\runtime.log"
        throw "WhisperApp exited immediately. Check: $tempLog and startup.log"
    }

    Write-Host ("WhisperApp started (python fallback PID {0})." -f $proc.Id)
}
catch {
    $_ | Out-String | Tee-Object -FilePath $startupLog -Append | Out-Host
    exit 1
}
finally {
    "==== $(Get-Date -Format s) Launcher end ====" | Out-File -FilePath $startupLog -Append -Encoding utf8
}

