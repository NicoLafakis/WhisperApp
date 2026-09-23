# WhisperApp Build Script
param(
    [switch]$Clean,
    [switch]$SkipInstall,
    [switch]$Installer,
    [switch]$Sign,
    [switch]$Release,
    [string]$Thumbprint,
    [string[]]$AllowedUpstreamThumbprints = @(),
    [string]$PfxPath,
    [string]$PfxPassword
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$AppName = 'WhisperApp'
$signScript = Join-Path $PSScriptRoot 'scripts\Sign-Binary.ps1'
$buildStarted = [DateTime]::UtcNow
if ($Release) {
    if (-not $Installer) { throw 'Release mode requires -Installer.' }
    if (-not $Sign) { throw 'Release mode requires -Sign.' }
    if (-not $Thumbprint -or $PfxPath) { throw 'Release mode requires a CurrentUser certificate thumbprint so Inno Setup can sign the installer and generated uninstaller.' }
    if ($AllowedUpstreamThumbprints | Where-Object { ($_ -replace '\s', '') -notmatch '^[A-Fa-f0-9]{40}$' }) { throw 'Every allowed upstream signer must be a 40-character certificate thumbprint.' }
    $Clean = $true
    & $signScript -Thumbprint $Thumbprint -ValidateCertificateOnly
}

function Write-Header([string]$text) { Write-Host "`n=== $text ===" -ForegroundColor Cyan }
function Find-SignToolPath {
    $command = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    $roots = @("${env:ProgramFiles(x86)}\Windows Kits\10\bin", "$env:ProgramFiles\Windows Kits\10\bin", "${env:ProgramFiles(x86)}\Windows Kits\10\App Certification Kit")
    foreach ($root in $roots) {
        if (Test-Path -LiteralPath $root) {
            $found = Get-ChildItem -LiteralPath $root -Filter signtool.exe -Recurse -ErrorAction SilentlyContinue | Where-Object FullName -Match '\\x64\\' | Select-Object -First 1
            if ($found) { return $found.FullName }
        }
    }
    throw 'SignTool is required for a signed release; install the Windows SDK or App Certification Kit.'
}
function Find-InnoCompiler {
    $command = Get-Command iscc.exe -ErrorAction SilentlyContinue
    if ($command) { return $command.Source }
    foreach ($candidate in @("$env:LOCALAPPDATA\Programs\Inno Setup 6\iscc.exe", "${env:ProgramFiles(x86)}\Inno Setup 6\iscc.exe", "$env:ProgramFiles\Inno Setup 6\iscc.exe")) {
        if (Test-Path -LiteralPath $candidate) { return $candidate }
    }
    return $null
}
. (Join-Path $PSScriptRoot 'scripts\Release-Signing.ps1')
if ($Release) {
    $null = Find-SignToolPath
    if (-not (Find-InnoCompiler)) { throw 'Inno Setup 6 compiler is required for -Release.' }
}

if ($Clean) {
    Write-Header 'Cleaning previous build outputs'
    foreach ($target in @('dist', 'build')) {
        $resolved = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $target))
        if (-not $resolved.StartsWith($PSScriptRoot, [StringComparison]::OrdinalIgnoreCase)) { throw "Refusing to clean path outside project: $resolved" }
        Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
    }
}

$python = if (Test-Path '.\.venv\Scripts\python.exe') { '.\.venv\Scripts\python.exe' } else { 'python' }
$pyinstaller = if (Test-Path '.\.venv\Scripts\pyinstaller.exe') { '.\.venv\Scripts\pyinstaller.exe' } else { 'pyinstaller' }
if (-not $SkipInstall) {
    Write-Header 'Installing dependencies'
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
    & $python -m pip install pyinstaller
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller installation failed.' }
}

Write-Header 'Building WhisperApp (PyInstaller onedir)'
& $pyinstaller WhisperApp.spec --clean
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }
$payload = Join-Path $PSScriptRoot 'dist\WhisperApp'
$exePath = Join-Path $payload 'WhisperApp.exe'
if (-not (Test-Path -LiteralPath $exePath)) { throw "Build failed; required executable missing: $exePath" }
$marker = if ($Release) { "RELEASE CANDIDATE - VERIFY SIGNATURES AND COMPLETE WINDOWS CHECKLIST BEFORE DISTRIBUTION`r`nBuilt UTC: $($buildStarted.ToString('o'))`r`n" } else { "UNSIGNED DEVELOPMENT BUILD - NOT FOR RELEASE`r`nBuilt UTC: $($buildStarted.ToString('o'))`r`n" }
Set-Content -LiteralPath (Join-Path $PSScriptRoot 'dist\BUILD-INFO.txt') -Value $marker -Encoding utf8

if ($Sign) {
    if (-not $Thumbprint) { throw 'Signing requires -Thumbprint.' }
    $releaseThumbprint = ($Thumbprint -replace '\s', '').ToUpperInvariant()
    $peFiles = @(Get-ChildItem -LiteralPath $payload -Recurse -File | Where-Object { $_.Extension -in @('.exe', '.dll', '.pyd') })
    if (-not $peFiles) { throw 'No native PE files found in the onedir payload.' }
    foreach ($file in $peFiles) {
        $existing = Get-AuthenticodeSignature -LiteralPath $file.FullName
        if ($existing.Status -eq 'Valid') {
            if (-not $existing.TimeStamperCertificate) { throw "Existing signature has no timestamp: $($file.FullName)" }
            $requiredSigner = if ($file.FullName -eq $exePath) { $releaseThumbprint } else { $null }
            Assert-ReleaseArtifactSigner -SignerThumbprint $existing.SignerCertificate.Thumbprint `
                -ReleaseThumbprint $releaseThumbprint -AllowedUpstreamThumbprints $AllowedUpstreamThumbprints `
                -RequiredSignerThumbprint $requiredSigner
            Write-Host "Preserving existing timestamped signature: $($file.FullName)"
        } elseif ($existing.Status -ne 'NotSigned') {
            throw "Existing PE signature is invalid; refusing to replace it: $($file.FullName) ($($existing.Status))"
        } else {
            & $signScript -FilePath $file.FullName -Thumbprint $Thumbprint
            if ($LASTEXITCODE -ne 0) { throw "Signing failed: $($file.FullName)" }
        }
    }
}

if ($Installer) {
    $iscc = Find-InnoCompiler
    if (-not $iscc) { throw 'Inno Setup 6 compiler is required for -Installer.' }
    $installerDir = Join-Path $PSScriptRoot 'installer'
    $installerPath = Join-Path $installerDir 'WhisperApp-Setup-1.1.0.exe'
    if (Test-Path $installerPath) { Remove-Item -LiteralPath $installerPath -Force }
    $isccArgs = @()
    if ($Release) {
        $isccArgs += '/DReleaseSigning=1'
        $tool = Join-Path $PSScriptRoot 'scripts\InnoSign.ps1'
        $command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$tool`" -Thumbprint $Thumbprint -FilePath `$f"
        $isccArgs += "/SWhisperAppRelease=$command"
    }
    $isccArgs += 'installer.iss'
    & $iscc @isccArgs
    if ($LASTEXITCODE -ne 0) { throw "Inno Setup compilation failed with exit code $LASTEXITCODE." }
    if (-not (Test-Path -LiteralPath $installerPath)) { throw 'Inno Setup did not produce a fresh installer.' }
    if ($Release) {
        $signtool = Find-SignToolPath
        $verifyScript = Join-Path $PSScriptRoot 'scripts\Verify-Release.ps1'
        & $verifyScript -Path @($peFiles.FullName) -SignToolPath $signtool -BuildStarted $buildStarted `
            -ReleaseThumbprint $releaseThumbprint -AllowedUpstreamThumbprints $AllowedUpstreamThumbprints
        & $verifyScript -Path @($installerPath) -SignToolPath $signtool -BuildStarted $buildStarted `
            -ReleaseThumbprint $releaseThumbprint -RequiredSignerThumbprint $releaseThumbprint

        # Install into an isolated temporary directory and verify the generated uninstaller too.
        $installRoot = Join-Path ([IO.Path]::GetTempPath()) ("WhisperApp-release-" + [guid]::NewGuid().ToString('N'))
        try {
            $process = Start-Process -FilePath $installerPath -ArgumentList @('/VERYSILENT', '/SUPPRESSMSGBOXES', '/NORESTART', "/DIR=`"$installRoot`"") -Wait -PassThru
            if ($process.ExitCode -ne 0) { throw "Release verification install failed: $($process.ExitCode)" }
            $installedPe = @(Get-ChildItem -LiteralPath $installRoot -Recurse -File | Where-Object { $_.Extension -in @('.exe', '.dll', '.pyd') })
            $uninstaller = Join-Path $installRoot 'unins000.exe'
            if (-not (Test-Path $uninstaller)) { throw 'Generated uninstaller is missing.' }
            & $verifyScript -Path @($installedPe.FullName) -SignToolPath $signtool -BuildStarted $buildStarted `
                -ReleaseThumbprint $releaseThumbprint -AllowedUpstreamThumbprints $AllowedUpstreamThumbprints
            & $verifyScript -Path @($uninstaller) -SignToolPath $signtool -BuildStarted $buildStarted `
                -ReleaseThumbprint $releaseThumbprint -RequiredSignerThumbprint $releaseThumbprint
        } finally {
            if (Test-Path $installRoot) { Remove-Item -LiteralPath $installRoot -Recurse -Force }
        }
        Set-Content -LiteralPath (Join-Path $PSScriptRoot 'dist\BUILD-INFO.txt') -Value $marker -Encoding utf8
    }
}

if ($Release) { Write-Host 'Release artifacts passed signature, timestamp, and SignTool verification.' -ForegroundColor Green }
else { Write-Warning 'Development build is unsigned and is not a release artifact.' }
