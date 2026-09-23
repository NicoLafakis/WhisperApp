; WhisperApp Inno Setup Installer Script
; Requires Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
; Usage: Compile with ISCC.exe installer.iss

#define MyAppName "WhisperApp"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "WhisperApp"
#define MyAppExeName "WhisperApp\WhisperApp.exe"
#define MyAppMutex "WhisperApp-SingleInstance-0f6b1c94b7d24e0a,Local\WhisperApp-SingleInstance-0f6b1c94b7d24e0a"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/NicoLafakis/WhisperApp
AppSupportURL=https://github.com/NicoLafakis/WhisperApp
AppUpdatesURL=https://github.com/NicoLafakis/WhisperApp
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE.txt
OutputDir=installer
OutputBaseFilename=WhisperApp-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
MinVersion=10.0

; Windows VersionInfo metadata (avoids generic or empty PE headers flagged by AV heuristics)
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} Setup
VersionInfoCopyright=Copyright (C) 2026 {#MyAppPublisher}
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

; Native Windows process management via Mutex and WM_CLOSE (avoids forced external process termination scripts)
AppMutex={#MyAppMutex}
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no
#ifdef ReleaseSigning
SignedUninstaller=yes
SignTool=WhisperAppRelease
#endif
[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startup"; Description: "Start WhisperApp on Windows login"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\BUILD-INFO.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyAppName}\*"; DestDir: "{app}\{#MyAppName}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: startup

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

; Preserve encrypted settings and user dictation data across uninstall/reinstall.
; The user can remove those files explicitly when they want to erase their data.
