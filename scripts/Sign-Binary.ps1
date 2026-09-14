<#
.SYNOPSIS
    Digitally signs Windows executables and installers with Authenticode & RFC 3161 timestamps.
.DESCRIPTION
    Signs .exe files using Microsoft SignTool (signtool.exe), applying SHA256 hashing
    and a trusted RFC 3161 timestamp (DigiCert). This complies with Windows Authenticode
    security standards and prevents antivirus heuristic blocking.
.PARAMETER FilePath
    Path or array of paths to .exe or .dll files to sign.
.PARAMETER Thumbprint
    Certificate SHA1 thumbprint from the Windows Certificate Store.
.PARAMETER PfxPath
    Optional path to a .pfx certificate file (e.g., commercial OV/EV certificate).
.PARAMETER PfxPassword
    Password for the .pfx file.
.PARAMETER TimestampServer
    RFC 3161 timestamp server URL (defaults to DigiCert).
#>

param(
    [Parameter(Mandatory=$true, ValueFromPipeline=$true)]
    [string[]]$FilePath,

    [string]$Thumbprint,
    [string]$PfxPath,
    [string]$PfxPassword,
    [string]$TimestampServer = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"

function Find-SignTool {
    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $knownPaths = @(
        "${env:ProgramFiles(x86)}\Windows Kits\10\App Certification Kit\signtool.exe",
        "${env:ProgramFiles}\Windows Kits\10\App Certification Kit\signtool.exe"
    )
    foreach ($path in $knownPaths) {
        if (Test-Path $path) { return $path }
    }

    # Search Windows Kits bin directory
    $sdkBins = Get-ChildItem "${env:ProgramFiles(x86)}\Windows Kits\10\bin" -Filter "signtool.exe" -Recurse -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -like "*x64*" } |
        Select-Object -First 1
    if ($sdkBins) { return $sdkBins.FullName }

    throw "signtool.exe not found. Please install Windows 10/11 SDK or App Certification Kit."
}

$signtool = Find-SignTool
Write-Host "Using SignTool: $signtool" -ForegroundColor Cyan

# Resolve certificate if not specified
if (-not $PfxPath -and -not $Thumbprint) {
    $cert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*CN=WhisperApp*" } | Select-Object -First 1
    if (-not $cert) {
        Write-Host "No existing WhisperApp Code Signing certificate found. Creating dev certificate..." -ForegroundColor Yellow
        $scriptPath = Join-Path $PSScriptRoot "Create-DevCert.ps1"
        $Thumbprint = & $scriptPath
    } else {
        $Thumbprint = $cert.Thumbprint
        Write-Host "Using existing certificate: $Thumbprint ($($cert.Subject))" -ForegroundColor Green
    }
}

foreach ($target in $FilePath) {
    $resolvedPath = Resolve-Path $target -ErrorAction SilentlyContinue
    if (-not $resolvedPath -or -not (Test-Path $resolvedPath)) {
        Write-Warning "File not found: $target"
        continue
    }

    Write-Host "`nSigning: $resolvedPath" -ForegroundColor Cyan

    $signArgs = @("sign", "/fd", "SHA256")

    if ($TimestampServer) {
        $signArgs += @("/tr", $TimestampServer, "/td", "SHA256")
    }

    if ($PfxPath) {
        $signArgs += @("/f", (Resolve-Path $PfxPath).Path)
        if ($PfxPassword) {
            $signArgs += @("/p", $PfxPassword)
        }
    } else {
        $signArgs += @("/sha1", $Thumbprint)
    }

    $signArgs += $resolvedPath.Path

    & $signtool @signArgs
    if ($LASTEXITCODE -ne 0) {
        throw "SignTool failed for $resolvedPath with exit code $LASTEXITCODE"
    }

    # Verify signature
    $sig = Get-AuthenticodeSignature $resolvedPath.Path
    Write-Host "Signed successfully:" -ForegroundColor Green
    Write-Host "  Signer: $($sig.SignerCertificate.Subject)"
    Write-Host "  Status: $($sig.Status) ($($sig.StatusMessage))"
    if ($sig.TimeStamperCertificate) {
        Write-Host "  Timestamp: $($sig.TimeStamperCertificate.Subject)"
    }
}
