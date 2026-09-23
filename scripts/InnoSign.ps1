param([Parameter(Mandatory=$true)][string]$FilePath, [Parameter(Mandatory=$true)][string]$Thumbprint)
$ErrorActionPreference = 'Stop'
& (Join-Path $PSScriptRoot 'Sign-Binary.ps1') -FilePath $FilePath -Thumbprint $Thumbprint
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Signing failed with exit code $LASTEXITCODE" }
