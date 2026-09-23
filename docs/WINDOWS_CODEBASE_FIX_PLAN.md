# Windows codebase fix plan

**Status:** Implementation completed; environment-dependent release validation outstanding
**Scope:** WhisperApp Windows desktop app, its tests, and the installable release pipeline
**Review basis:** Original source-review snapshot; implementation verification and the remaining Windows release checks are recorded below.

## Goal

Close the confirmed reliability and usability gaps before treating WhisperApp as ready for broader Windows installation. Keep dictation audio and transcripts recoverable, keep Settings responsive during network operations, make automated tests safe to run, and make release artifacts verifiably signed when a publicly trusted publisher identity is available.

## Load-bearing invariant

**A temporary failure, invalid settings file, app shutdown, or release-build error must not silently discard user dictation or produce an artifact that is presented as a verified release.** Audio remains recoverable on disk, failures are visible, and release verification fails closed.

## In scope

1. Run the API-key capability check without blocking the Qt UI.
2. Make settings persistence resilient to interrupted writes and malformed JSON shapes.
3. Make certificate-related tests safe and portable; keep certificate-store modification opt-in and out of the normal test suite.
4. Define and implement a release verification path for the app executable, installer, uninstaller, and bundled native binaries.
5. Add regression coverage for the confirmed issues and document Windows-only manual verification that cannot run in ordinary CI.

## Out of scope

- Changing transcription models, hotkey semantics, audio format, or the documented clipboard behavior.
- Replacing the transcription provider or adding a new paid signing service.
- Purchasing or provisioning a publicly trusted signing certificate.
- Claiming Smart App Control acceptance from an Authenticode status check alone.

The `auto_copy` setting has legacy behavior explicitly documented in `docs/REVERSE_ENGINEERED_PRD.md`: text is copied to the clipboard to enable paste even when the setting is disabled. Preserve that behavior unless product requirements are deliberately revised in a separate change.

## Work items

### 1. Keep Settings responsive during API-key checks

**Current behavior:** `SettingsDialog._test_api_key` calls the network synchronously. The HTTP client timeout is 60 seconds, which can freeze the dialog during a slow connection.

**Required change:** Execute the check on a worker thread and return a structured result to the UI through Qt signals. Disable the check button only while the request is active. Restore button state and cursor on both success and failure. Do not access widgets from the worker thread. Prevent starting duplicate checks; closing the dialog must not destroy a running `QThread`.

**Acceptance criteria:**

- The dialog continues processing events while the API check is pending.
- Success, quota/auth errors, connection errors, and timeout all produce the existing actionable result message.
- The button and cursor return to their normal state for every outcome.
- Closing Settings while a check is running does not cause a Qt thread-destruction warning or process crash.
- Unit tests cover successful and failed completion, UI state restoration, and dialog-close behavior without making network requests.

### 2. Make configuration writes recoverable

**Current behavior:** `ConfigManager._write_settings` overwrites `config.json` directly. An interrupted write can leave invalid JSON; startup then replaces it with defaults. A syntactically valid JSON value that is not an object can also fail at `settings.update(data)`.

**Required change:** Validate that the loaded JSON top level is an object before applying defaults. Write settings through a temporary file in the same directory, flush it, and atomically replace the target. On malformed or unsupported configuration, preserve the original file for recovery and load safe defaults in memory; log a clear, non-secret diagnostic. Do not log the API key or encrypted value.

**Acceptance criteria:**

- Object-shaped settings continue to load and preserve existing migration behavior.
- Arrays, strings, numbers, `null`, malformed JSON, and unreadable settings do not crash app startup.
- A failed write leaves the last valid `config.json` intact.
- Invalid settings are preserved under a recoverable filename or equivalent backup mechanism instead of being silently overwritten.
- Tests prove the API key is never written in plaintext and is never included in log output.

### 3. Make certificate tests safe to run

**Current behavior:** `tests/test_security_compliance.py::test_dev_cert_generation_and_export` launches a script that creates a certificate, modifies the current user's certificate stores, and writes into `assets/`. It failed in this environment before those side effects because `Get-ChildItem -CodeSigningCert` was rejected.

**Required change:** Normal automated tests must not create certificates, alter certificate stores, or overwrite repository assets. Test certificate policy through synthetic certificate objects or an isolated temporary test fixture. If the development-certificate script remains supported, make its trust-store installation an explicit opt-in action and update its certificate lookup to work on the supported Windows PowerShell version.

**Acceptance criteria:**

- Running the standard test command makes no changes to Windows certificate stores or tracked assets.
- Certificate-policy tests run without a real certificate or signing credential.
- Any manual development-certificate install clearly states which user stores it modifies and how to remove the certificate.
- The test suite passes on the project's documented Windows/Python versions.

### 4. Add a fail-closed release verification path

**Current state:** `dist/WhisperApp.exe` and `installer/WhisperApp-Setup-1.1.0.exe` are both unsigned. The release guide also identifies unverified bundled native binaries and an unsigned generated uninstaller. Signing the outer executable and installer alone does not satisfy those remaining checks.

**Required change:** Define a release command or mode separate from local development builds. It must fail unless every required release artifact is present, signed with the configured release identity, has a valid timestamped signature, and passes SignTool verification. Include the generated uninstaller and all shipped native PE binaries in the signing/verification plan. Do not allow stale outputs from a prior build to satisfy release checks. Preserve valid upstream signatures where appropriate. Keep local unsigned builds available for development, but label them clearly as non-release artifacts.

**Implementation decision:** Before changing PyInstaller layout, inspect the current one-file payload and Inno Setup signing options. Choose a packaging layout that allows every required PE file and the generated uninstaller to be signed and verified. Record the chosen approach in the release documentation and test it with the project's supported Inno Setup version.

**External dependency:** A publicly trusted RSA code-signing identity and its private-key access are required to produce the final signed artifacts. The implementation can add checks and fail-closed automation without those credentials, but cannot produce or validate a publicly trusted release until the identity is provisioned.

**Acceptance criteria:**

- A local developer build can still be produced without release credentials and cannot be mistaken for a verified release.
- Release mode fails before publishing/copying artifacts if credentials, signing tools, expected files, timestamps, or verification are missing.
- The release check detects an unsigned executable, installer, uninstaller, or bundled native binary.
- The installer does not silently reuse an old setup executable after a failed or missing compilation.
- A release checklist records installation, launch, microphone, hotkey, transcription, paste, upgrade, uninstall, and Smart App Control checks on supported Windows versions.
- No documentation promises antivirus acceptance solely because signing succeeded.

## Verification plan

### Automated

- Run the full pytest suite with a writable isolated `--basetemp` directory.
- Add focused tests for the four work items above; keep all network calls mocked.
- Run PowerShell parser checks for build/signing scripts where the supported PowerShell runtime is available.
- Run the release verifier against unsigned fixtures, malformed outputs, stale outputs, and test certificates without modifying certificate stores.

### Windows manual checks

These require a Windows test machine and, for release signing, the provisioned publisher identity:

- Build and install as a standard user and as an administrator if that install mode remains supported.
- Launch from the installed shortcut; verify the tray icon, settings, duplicate-instance behavior, microphone selection, hotkey recording, transcription, and paste.
- Upgrade an existing installation and verify settings and dictation history remain available.
- Uninstall and verify the documented user-data retention behavior.
- Verify signatures and timestamps on the installer, installed app, uninstaller, and required bundled native files.
- Exercise installation and launch with Smart App Control enabled; review Code Integrity logs and record the outcome.

## Acceptance checklist

- [x] API-key checks run off the UI thread and active threads are retained until completion.
- [x] Settings writes are atomic; malformed settings are backed up and do not crash startup.
- [x] The default automated test suite does not install certificates or write repository assets.
- [x] Release mode distinguishes unsigned development builds from release candidates.
- [x] Release verification covers the executable, installer, generated uninstaller, and bundled native binaries and rejects stale outputs.
- [x] Automated tests pass; Windows-only checks and credential-dependent blockers are recorded honestly.
- [x] Existing clipboard behavior and the user's working-tree changes are preserved.

## Known verification limits

The remediation test run passed 115 tests on 2026-09-23. Inno Setup, SignTool, and a publicly trusted signing identity are environment dependencies; without them, real installer compilation, code-signing calls, temporary installation, and Windows Smart App Control checks cannot be completed. The implementation fails closed in those cases and reports that no trusted release was produced.
