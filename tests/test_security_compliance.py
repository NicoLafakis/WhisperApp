import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pyinstaller_spec_security_settings():
    spec_path = ROOT / "WhisperApp.spec"
    assert spec_path.exists(), "WhisperApp.spec must exist"
    content = spec_path.read_text(encoding="utf-8")

    # upx=True is the #1 trigger for heuristic AV flags on Windows (McAfee Artemis, RealProtect, etc.)
    assert re.search(r"upx\s*=\s*False", content), "WhisperApp.spec must set upx=False to prevent AV packer flags"
    assert not re.search(r"upx\s*=\s*True", content), "WhisperApp.spec must not enable UPX"

    # Explicit application manifest to guarantee Windows UAC execution level and compatibility GUIDs
    assert "manifest=" in content, "WhisperApp.spec must specify an application manifest"


def test_windows_manifest_conformance():
    manifest_path = ROOT / "assets" / "WhisperApp.manifest"
    assert manifest_path.exists(), "assets/WhisperApp.manifest must exist"

    xml_text = manifest_path.read_text(encoding="utf-8")
    root = ET.fromstring(xml_text)

    # Check namespaces
    # Trust info / requestedExecutionLevel
    assert "asInvoker" in xml_text, "Manifest must declare requestedExecutionLevel 'asInvoker'"
    assert 'uiAccess="false"' in xml_text, "Manifest uiAccess must be false"

    # Windows 10/11 compatibility GUID: {8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}
    assert "{8e0f7a12-bfb3-4fe8-b9a5-48fd50a15a9a}" in xml_text, "Manifest must include Windows 10/11 supportedOS GUID"


def test_installer_iss_security_and_integrity():
    iss_path = ROOT / "installer.iss"
    assert iss_path.exists(), "installer.iss must exist"
    content = iss_path.read_text(encoding="utf-8")

    # 1. Source executable must point to current dist output, not stale dist\gpt-transcribe
    assert 'Source: "dist\\{#MyAppExeName}"' in content, (
        "installer.iss must package 'dist\\{#MyAppExeName}', not stale directories"
    )
    assert "dist\\gpt-transcribe" not in content, "installer.iss must not point to obsolete dist\\gpt-transcribe"

    # 2. Heuristic red flag: taskkill via cmd in [UninstallRun]
    assert "taskkill" not in content, (
        "installer.iss must not invoke taskkill via cmd.exe, which triggers AV heuristic detection"
    )

    # 3. Native Inno Setup process management
    assert re.search(r"CloseApplications\s*=\s*yes", content, re.IGNORECASE), (
        "installer.iss must use native CloseApplications=yes for clean application termination"
    )

    # 4. AppMutex must protect the application
    assert re.search(r"AppMutex\s*=", content, re.IGNORECASE), "installer.iss must define AppMutex"
    assert "WhisperApp-SingleInstance-0f6b1c94b7d24e0a" in content, (
        "installer.iss AppMutex must match the single instance mutex used in main.py"
    )

    # 5. Full Windows VersionInfo metadata in installer header
    assert re.search(r"VersionInfoVersion\s*=", content), "installer.iss must define VersionInfoVersion"
    assert re.search(r"VersionInfoCompany\s*=", content), "installer.iss must define VersionInfoCompany"
    assert re.search(r"VersionInfoDescription\s*=", content), "installer.iss must define VersionInfoDescription"
    assert re.search(r"VersionInfoCopyright\s*=", content), "installer.iss must define VersionInfoCopyright"
    assert re.search(r"VersionInfoProductName\s*=", content), "installer.iss must define VersionInfoProductName"
    assert re.search(r"VersionInfoProductVersion\s*=", content), "installer.iss must define VersionInfoProductVersion"


def test_uninstall_does_not_erase_user_settings_or_dictation():
    content = (ROOT / "installer.iss").read_text(encoding="utf-8")
    section = ""
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("["):
            section = line.lower()
        if section == "[uninstalldelete]" and line and not line.startswith((";", "[")):
            assert ".whisperapp" not in line.lower()
            assert "{userdocs}" not in line.lower()


def test_powershell_scripts_syntax():
    """Verify that all PowerShell scripts in the project parse without syntax/drive errors."""
    import subprocess
    ps_scripts = list(ROOT.glob("*.ps1")) + list((ROOT / "scripts").glob("*.ps1"))
    assert len(ps_scripts) >= 2, "Must find build.ps1 and scripts/*.ps1"

    for script in ps_scripts:
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            f"$content = Get-Content -Raw '{script}'; "
            "$tokens = $null; $errors = $null; "
            "[System.Management.Automation.Language.Parser]::ParseInput($content, [ref]$tokens, [ref]$errors) | Out-Null; "
            "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_.Message }; exit 1 }"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        assert res.returncode == 0, f"PowerShell syntax error in {script.name}:\n{res.stderr}"


def test_version_consistency_across_metadata():
    """Verify that whisperapp.__version__ matches installer.iss, version_info.txt, and WhisperApp.manifest."""
    import whisperapp
    version = whisperapp.__version__

    # 1. installer.iss
    iss_text = (ROOT / "installer.iss").read_text(encoding="utf-8")
    assert f'#define MyAppVersion "{version}"' in iss_text, (
        f"installer.iss MyAppVersion must match whisperapp.__version__ ({version})"
    )

    # 2. version_info.txt
    vinfo_text = (ROOT / "version_info.txt").read_text(encoding="utf-8")
    assert f"FileVersion', u'{version}.0')" in vinfo_text or f"FileVersion', u'{version}')" in vinfo_text, (
        f"version_info.txt FileVersion must match whisperapp.__version__ ({version})"
    )

    # 3. WhisperApp.manifest
    manifest_text = (ROOT / "assets" / "WhisperApp.manifest").read_text(encoding="utf-8")
    assert f'version="{version}.0"' in manifest_text or f'version="{version}"' in manifest_text, (
        f"WhisperApp.manifest version must match whisperapp.__version__ ({version})"
    )


def test_dev_cert_generation_and_export():
    """Verify scripts/Create-DevCert.ps1 runs cleanly and exports assets/WhisperApp-Dev.cer."""
    import subprocess
    script_path = ROOT / "scripts" / "Create-DevCert.ps1"
    assert script_path.exists(), "scripts/Create-DevCert.ps1 must exist"

    cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script_path)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    assert res.returncode == 0, f"Create-DevCert.ps1 failed with code {res.returncode}:\n{res.stderr}\n{res.stdout}"

    cer_path = ROOT / "assets" / "WhisperApp-Dev.cer"
    assert cer_path.exists(), f"assets/WhisperApp-Dev.cer must be generated by Create-DevCert.ps1"
    assert cer_path.stat().st_size > 0, "WhisperApp-Dev.cer must not be empty"
