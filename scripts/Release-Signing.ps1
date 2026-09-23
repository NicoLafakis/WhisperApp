# Local preflight only: a locally trusted chain does not establish Microsoft public trust.
function Assert-ReleaseCertificate($Certificate) {
    if (-not $Certificate -or -not $Certificate.HasPrivateKey) {
        throw 'Release certificate must have an accessible private key.'
    }
    if ($Certificate.Subject -eq $Certificate.Issuer) {
        throw 'Release certificate cannot be self-signed. Obtain a publicly trusted publisher certificate.'
    }
    if ($Certificate.PublicKey.Oid.Value -ne '1.2.840.113549.1.1.1') {
        throw 'Release certificate must use RSA for Smart App Control.'
    }
    $now = Get-Date
    if ($Certificate.NotBefore -gt $now -or $Certificate.NotAfter -le $now) {
        throw 'Release certificate is outside its validity period.'
    }
    $codeSigning = @($Certificate.EnhancedKeyUsageList | Where-Object { $_.ObjectId.Value -eq '1.3.6.1.5.5.7.3.3' })
    if ($codeSigning.Count -eq 0) {
        throw 'Release certificate must include the code-signing extended key usage.'
    }
}

function Assert-ReleaseArtifactSigner {
    param(
        [string]$SignerThumbprint,
        [string]$ReleaseThumbprint,
        [string[]]$AllowedUpstreamThumbprints = @(),
        [string]$RequiredSignerThumbprint
    )
    $actual = ($SignerThumbprint -replace '\s', '').ToUpperInvariant()
    $release = ($ReleaseThumbprint -replace '\s', '').ToUpperInvariant()
    if ($actual -notmatch '^[A-F0-9]{40}$' -or $release -notmatch '^[A-F0-9]{40}$') {
        throw 'Release signer thumbprint is missing or malformed.'
    }
    if ($RequiredSignerThumbprint) {
        $required = ($RequiredSignerThumbprint -replace '\s', '').ToUpperInvariant()
        if ($actual -ne $required) { throw "Artifact signer does not match required release identity: $actual" }
        return
    }
    $allowed = @($release) + @($AllowedUpstreamThumbprints | ForEach-Object { ($_ -replace '\s', '').ToUpperInvariant() })
    if ($actual -notin $allowed) {
        throw "Artifact signer is neither the configured release identity nor an explicitly allowed upstream signer: $actual"
    }
}
