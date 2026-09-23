param(
    [Parameter(Mandatory=$true)][string[]]$Path,
    [Parameter(Mandatory=$true)][string]$SignToolPath,
    [Parameter(Mandatory=$true)][datetime]$BuildStarted,
    [Parameter(Mandatory=$true)][string]$ReleaseThumbprint,
    [string[]]$AllowedUpstreamThumbprints = @(),
    [string]$RequiredSignerThumbprint
)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'Release-Signing.ps1')
foreach ($item in $Path) {
    if (-not (Test-Path -LiteralPath $item -PathType Leaf)) { throw "Required release artifact missing: $item" }
    $file = Get-Item -LiteralPath $item
    if ($file.LastWriteTimeUtc -lt $BuildStarted.ToUniversalTime()) { throw "Stale release artifact rejected: $item" }
    $signature = Get-AuthenticodeSignature -LiteralPath $file.FullName
    if ($signature.Status -ne 'Valid' -or -not $signature.TimeStamperCertificate) {
        throw "Artifact lacks a valid timestamped Authenticode signature: $item ($($signature.Status))"
    }
    Assert-ReleaseArtifactSigner -SignerThumbprint $signature.SignerCertificate.Thumbprint `
        -ReleaseThumbprint $ReleaseThumbprint -AllowedUpstreamThumbprints $AllowedUpstreamThumbprints `
        -RequiredSignerThumbprint $RequiredSignerThumbprint
    & $SignToolPath verify /pa /all /v $file.FullName
    if ($LASTEXITCODE -ne 0) { throw "SignTool verification failed: $item" }
}
Write-Host "Verified $($Path.Count) timestamped release artifacts."
