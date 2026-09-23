<#
.SYNOPSIS
    Digitally signs Windows executables and installers with Authenticode & RFC 3161 timestamps.
.DESCRIPTION
    Signs .exe files using Microsoft SignTool (signtool.exe), applying SHA256 hashing
    and a trusted RFC 3161 timestamp (DigiCert). This complies with Windows Authenticode
    integrity checks. Signing does not guarantee antivirus or Smart App Control acceptance.
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
    [Parameter(ValueFromPipeline=$true)]
    [string[]]$FilePath,

    [string]$Thumbprint,
    [string]$PfxPath,
    [string]$PfxPassword,
    [string]$TimestampServer = "http://timestamp.digicert.com",
    [switch]$ValidateCertificateOnly
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

. (Join-Path $PSScriptRoot 'Release-Signing.ps1')
if ((-not $PfxPath -and -not $Thumbprint) -or ($PfxPath -and $Thumbprint)) {
    throw 'Specify exactly one publicly trusted release certificate using -Thumbprint or -PfxPath. Development certificates are not accepted.'
}
if ($PfxPath) {
    $cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
    try {
        $cert.Import((Resolve-Path -LiteralPath $PfxPath).Path, $PfxPassword, [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::EphemeralKeySet)
        Assert-ReleaseCertificate $cert
    } finally {
        $cert.Dispose()
    }
} else {
    $Thumbprint = $Thumbprint.Replace(' ', '')
    if ($Thumbprint -notmatch '^[A-Fa-f0-9]{40}$') { throw 'Invalid certificate thumbprint.' }
    $cert = Get-Item -LiteralPath "Cert:\CurrentUser\My\$Thumbprint" -ErrorAction Stop
    Assert-ReleaseCertificate $cert
}
if ($ValidateCertificateOnly) { return }
if (-not $FilePath) { throw 'At least one file is required for signing.' }
if (-not $TimestampServer) { throw 'A timestamp server is required for release signing.' }
$signtool = Find-SignTool
Write-Host "Using SignTool: $signtool" -ForegroundColor Cyan

foreach ($target in $FilePath) {
    $resolvedPath = Resolve-Path -LiteralPath $target -ErrorAction Stop
    if (-not $resolvedPath -or -not (Test-Path $resolvedPath)) {
        throw "File not found: $target"
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
    if ($sig.Status -ne 'Valid' -or -not $sig.TimeStamperCertificate) {
        throw "Release signature verification failed or timestamp missing: $resolvedPath ($($sig.Status))"
    }
    & $signtool verify /pa /all /v $resolvedPath.Path
    if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed: $resolvedPath" }
    Write-Host "Signed successfully:" -ForegroundColor Green
    Write-Host "  Signer: $($sig.SignerCertificate.Subject)"
    Write-Host "  Status: $($sig.Status) ($($sig.StatusMessage))"
    if ($sig.TimeStamperCertificate) {
        Write-Host "  Timestamp: $($sig.TimeStamperCertificate.Subject)"
    }
}
