"""Execute certificate policy checks without modifying certificate stores."""
import pathlib
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ReleaseCertificateTests(unittest.TestCase):
    def check_certificate(self, change, should_pass):
        helper = (ROOT / "scripts" / "Release-Signing.ps1").read_text(encoding="utf-8")
        script = f"""
        $ErrorActionPreference = 'Stop'
        {helper}
        $cert = [pscustomobject]@{{
            Subject = 'CN=Publisher'; Issuer = 'CN=Public CA'; HasPrivateKey = $true
            NotBefore = (Get-Date).AddDays(-1); NotAfter = (Get-Date).AddDays(30)
            PublicKey = [pscustomobject]@{{Oid=[pscustomobject]@{{Value='1.2.840.113549.1.1.1'}}}}
            EnhancedKeyUsageList = @([pscustomobject]@{{ObjectId=[pscustomobject]@{{Value='1.3.6.1.5.5.7.3.3'}}}})
        }}
        {change}
        Assert-ReleaseCertificate $cert
        """
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True)
        if should_pass:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Release certificate', result.stderr)

    def test_accepts_rsa_publisher_certificate(self):
        self.check_certificate('', True)

    def test_rejects_self_signed_certificate(self):
        self.check_certificate('$cert.Issuer = $cert.Subject', False)

    def test_rejects_ecc_certificate(self):
        self.check_certificate("$cert.PublicKey.Oid.Value = '1.2.840.10045.2.1'", False)

    def test_rejects_missing_private_key(self):
        self.check_certificate('$cert.HasPrivateKey = $false', False)

    def test_rejects_expired_certificate(self):
        self.check_certificate('$cert.NotAfter = (Get-Date).AddDays(-1)', False)

    def test_rejects_future_certificate(self):
        self.check_certificate('$cert.NotBefore = (Get-Date).AddDays(1)', False)

    def test_rejects_wrong_usage(self):
        self.check_certificate("$cert.EnhancedKeyUsageList[0].ObjectId.Value = '1.3.6.1.5.5.7.3.1'", False)

    def check_signer(self, signer, allowed, required=None, should_pass=True):
        helper = (ROOT / 'scripts' / 'Release-Signing.ps1').read_text(encoding='utf-8')
        required_arg = f"-RequiredSignerThumbprint '{required}'" if required else ''
        script = f"""
        $ErrorActionPreference = 'Stop'
        {helper}
        Assert-ReleaseArtifactSigner -SignerThumbprint '{signer}' -ReleaseThumbprint '{'A' * 40}' `
            -AllowedUpstreamThumbprints @({', '.join(repr(value) for value in allowed)}) {required_arg}
        """
        result = subprocess.run(['powershell', '-NoProfile', '-NonInteractive', '-Command', script], capture_output=True, text=True)
        if should_pass:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0)

    def test_configured_publisher_signature_is_allowed(self):
        self.check_signer('a' * 40, [])

    def test_only_explicitly_allowlisted_upstream_signature_is_allowed(self):
        self.check_signer('b' * 40, ['b' * 40])
        self.check_signer('b' * 40, [], should_pass=False)

    def test_required_artifacts_reject_other_signers_even_if_allowlisted(self):
        self.check_signer('b' * 40, ['b' * 40], required='a' * 40, should_pass=False)

    def test_release_verifier_rejects_unsigned_fixture(self):
        module_check = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
             '-Command', 'Get-AuthenticodeSignature -? | Out-Null'],
            capture_output=True, text=True,
        )
        if module_check.returncode != 0:
            self.skipTest('Microsoft.PowerShell.Security is unavailable in this PowerShell host')
        with tempfile.TemporaryDirectory() as directory:
            fixture = pathlib.Path(directory) / 'unsigned.exe'
            fixture.write_bytes(b'MZ' + b'\0' * 64)
            verifier = ROOT / 'scripts' / 'Verify-Release.ps1'
            result = subprocess.run([
                'powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(verifier),
                '-Path', str(fixture), '-SignToolPath', 'signtool.exe',
                '-BuildStarted', '2000-01-01T00:00:00Z', '-ReleaseThumbprint', 'A' * 40,
            ], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('timestamped Authenticode signature', result.stderr)

    def test_release_verifier_rejects_missing_and_stale_outputs(self):
        verifier = ROOT / 'scripts' / 'Verify-Release.ps1'
        with tempfile.TemporaryDirectory() as directory:
            fixture = pathlib.Path(directory) / 'unsigned.exe'
            fixture.write_bytes(b'MZ' + b'\0' * 64)
            missing = subprocess.run([
                'powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(verifier),
                '-Path', str(pathlib.Path(directory) / 'missing.exe'), '-SignToolPath', 'unused',
                '-BuildStarted', '2000-01-01T00:00:00Z', '-ReleaseThumbprint', 'A' * 40,
            ], capture_output=True, text=True)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn('Required release artifact missing', missing.stderr)

            stale = subprocess.run([
                'powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File', str(verifier),
                '-Path', str(fixture), '-SignToolPath', 'unused',
                '-BuildStarted', '2999-01-01T00:00:00Z', '-ReleaseThumbprint', 'A' * 40,
            ], capture_output=True, text=True)
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn('Stale release artifact rejected', stale.stderr)


if __name__ == '__main__':
    unittest.main()
