<#
.SYNOPSIS
    Generates and installs a local development Code Signing certificate for WhisperApp.
.DESCRIPTION
    Creates a self-signed X.509 code-signing certificate (SHA256, RSA 2048-bit),
    stores it in Cert:\CurrentUser\My, and registers it in TrustedPeople & TrustedPublisher.
    This enables Windows, SmartScreen, and Antivirus scanners (e.g. McAfee) to verify
    the Authenticode signature on locally built executables and installers.
#>

param(
    [string]$Subject = "CN=WhisperApp Developer, O=WhisperApp",
    [int]$ValidityYears = 5,
    [string]$CerExportPath = "$PSScriptRoot\..\assets\WhisperApp-Dev.cer"
)

$ErrorActionPreference = "Stop"

Write-Host "Checking for existing WhisperApp Code Signing certificate..." -ForegroundColor Cyan

$existingCert = Get-ChildItem Cert:\CurrentUser\My -CodeSigningCert | Where-Object { $_.Subject -like "*CN=WhisperApp*" } | Select-Object -First 1

if ($existingCert) {
    Write-Host "Found existing certificate: $($existingCert.Thumbprint) ($($existingCert.Subject))" -ForegroundColor Green
    $cert = $existingCert
} else {
    Write-Host "Generating new self-signed Code Signing certificate..." -ForegroundColor Yellow
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $Subject `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -HashAlgorithm "SHA256" `
        -KeyLength 2048 `
        -NotAfter (Get-Date).AddYears($ValidityYears)
    Write-Host "Created certificate: $($cert.Thumbprint)" -ForegroundColor Green
}

# Trust in CurrentUser\TrustedPeople and CurrentUser\TrustedPublisher
$stores = @("TrustedPeople", "TrustedPublisher")
foreach ($storeName in $stores) {
    try {
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeName, "CurrentUser")
        $store.Open("ReadWrite")
        $exists = $store.Certificates | Where-Object { $_.Thumbprint -eq $cert.Thumbprint }
        if (-not $exists) {
            $store.Add($cert)
            Write-Host "Added certificate to Cert:\CurrentUser\$storeName" -ForegroundColor Green
        } else {
            Write-Host "Certificate already present in Cert:\CurrentUser\$storeName" -ForegroundColor Gray
        }
        $store.Close()
    } catch {
        Write-Warning "Could not add to store ${storeName}: $_"
    }
}

# Export public .cer
if ($CerExportPath) {
    $cerDir = Split-Path -Parent $CerExportPath
    if (-not (Test-Path $cerDir)) {
        New-Item -ItemType Directory -Path $cerDir -Force | Out-Null
    }
    Export-Certificate -Cert $cert -FilePath $CerExportPath -Force | Out-Null
    Write-Host "Exported public certificate to: $CerExportPath" -ForegroundColor Green
}

Write-Host "`nThumbprint: $($cert.Thumbprint)" -ForegroundColor Cyan
Write-Host "Subject:    $($cert.Subject)" -ForegroundColor Cyan
return $cert.Thumbprint
