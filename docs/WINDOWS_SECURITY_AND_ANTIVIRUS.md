# Windows release signing and Smart App Control

## Signing identity

Use an RSA code-signing identity trusted by Microsoft's Trusted Root Program, or Microsoft Artifact Signing with a **Public Trust** profile. A self-signed certificate and private trust are unsuitable for distribution. Publisher identity verification must be completed with the provider.

A valid Authenticode signature or timestamp does not guarantee acceptance by antivirus products or Smart App Control. Test the shipped artifacts on supported Windows versions and inspect Code Integrity logs.

## Development certificates

`Create-DevCert.ps1` creates a certificate in `Cert:\CurrentUser\My` only when run manually. By default it does not add trust or export a certificate. `-InstallTrust` additionally changes `Cert:\CurrentUser\TrustedPeople` and `Cert:\CurrentUser\TrustedPublisher`; undo those changes by removing the certificate thumbprint from both stores. The script is not part of the release build and its certificate is rejected by release preflight.

## Build modes

Unsigned local builds are labeled and intended only for development:

```powershell
.\build.ps1 -Clean -SkipInstall
```

Release candidates require an explicit trusted certificate in `Cert:\CurrentUser\My`, Inno Setup, and SignTool:

```powershell
.\build.ps1 -Release -SkipInstall -Installer -Sign -Thumbprint 'YOUR_PUBLICLY_TRUSTED_CERTIFICATE_THUMBPRINT'
```

The release mode uses PyInstaller onedir. This makes every shipped `.exe`, `.dll`, and `.pyd` available for individual verification before Inno Setup packages it. Unsigned payload binaries are signed with the configured publisher identity. Existing timestamped upstream signatures are preserved only when their signer thumbprints are explicitly allowlisted with `-AllowedUpstreamThumbprints`; all other release files must match the configured publisher identity. The installer and generated uninstaller must match that identity exactly. Inno Setup's `SignedUninstaller=yes` and named SignTool integration sign both. After compilation, the build installs the package to a temporary directory and checks the installed payload and uninstaller with SignTool.

The release build cleans stale `dist`, `build`, and installer outputs first. It fails if the certificate, compiler, signing tools, timestamp, expected artifacts, signature verification, temporary install, or generated uninstaller is missing or invalid. The packaged build marker remains `RELEASE CANDIDATE` and asks for the manual checks below. No public-trust identity has been provisioned here, so no trusted release has been produced.

## Windows release checklist

- [ ] Confirm provider public trust and private-key access.
- [ ] Build the release candidate and retain the build log and artifact hashes.
- [ ] Install as a standard user; verify launch, tray icon, settings, duplicate-instance behavior, microphone selection, hotkey recording, transcription, and paste.
- [ ] Upgrade an existing installation; verify settings and dictation history remain available.
- [ ] Uninstall and verify the documented user-data retention behavior.
- [ ] On supported Windows versions with Smart App Control enabled, exercise installation and launch; inspect Code Integrity logs and record the outcome.
- [ ] Record provider or antivirus findings. A signature is not proof of acceptance.
