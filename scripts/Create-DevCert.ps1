<#
.SYNOPSIS
    Creates a local WhisperApp development signing certificate.
.DESCRIPTION
    The certificate is created in Cert:\CurrentUser\My. Trust-store changes are opt-in.
    -InstallTrust additionally modifies Cert:\CurrentUser\TrustedPeople and
    Cert:\CurrentUser\TrustedPublisher. Remove those copies and the My copy by
    thumbprint with Remove-Item Cert:\CurrentUser\<Store>\<Thumbprint>.
#>
param(
    [string]$Subject = "CN=WhisperApp Developer, O=WhisperApp",
    [int]$ValidityYears = 5,
    [string]$CerExportPath,
    [switch]$InstallTrust
)

$ErrorActionPreference = "Stop"

# Avoid the -CodeSigningCert provider parameter, which is not available in all
# supported Windows PowerShell versions.
$existingCert = Get-ChildItem -Path Cert:\CurrentUser\My | Where-Object {
    $_.Subject -like "*CN=WhisperApp*" -and $_.HasPrivateKey -and
    @($_.EnhancedKeyUsageList | Where-Object { $_.ObjectId.Value -eq '1.3.6.1.5.5.7.3.3' }).Count -gt 0
} | Select-Object -First 1

if ($existingCert) {
    $cert = $existingCert
} else {
    $cert = New-SelfSignedCertificate -Type CodeSigningCert -Subject $Subject `
        -CertStoreLocation "Cert:\CurrentUser\My" -HashAlgorithm "SHA256" `
        -KeyLength 2048 -NotAfter (Get-Date).AddYears($ValidityYears)
}

if ($InstallTrust) {
    foreach ($storeName in @("TrustedPeople", "TrustedPublisher")) {
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeName, "CurrentUser")
        try {
            $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
            if (-not ($store.Certificates | Where-Object Thumbprint -eq $cert.Thumbprint)) {
                $store.Add($cert)
            }
        } finally {
            $store.Close()
        }
    }
    Write-Warning "Installed in CurrentUser\TrustedPeople and CurrentUser\TrustedPublisher. Remove by thumbprint from both stores to undo."
}

if ($CerExportPath) {
    $cerDir = Split-Path -Parent $CerExportPath
    if ($cerDir -and -not (Test-Path $cerDir)) { New-Item -ItemType Directory -Path $cerDir -Force | Out-Null }
    Export-Certificate -Cert $cert -FilePath $CerExportPath -Force | Out-Null
}
Write-Host "Development certificate: $($cert.Thumbprint) ($($cert.Subject))"
return $cert.Thumbprint
