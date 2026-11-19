; Per-user Windows 10/11 installation. Client records remain outside the install directory.
[Setup]
AppId={{71AC4CF9-1FCE-4B68-B327-31CBA7478E62}
AppName=UV Security Manager
AppVersion=1.0.0
AppPublisher=UV Security System
AppPublisherURL=https://uv-security-system.satiny-coin-6290.chatgpt.site/
DefaultDirName={localappdata}\Programs\UVSecurityManager
DefaultGroupName=UV Security Manager
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=installer
OutputBaseFilename=UV-Security-Manager-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\UV-Security-Manager.exe
CloseApplications=yes
SetupLogging=yes

[Files]
Source: "dist\UV-Security-Manager.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "QUICK-START.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{userdesktop}\UV Security Manager"; Filename: "{app}\UV-Security-Manager.exe"
Name: "{group}\UV Security Manager"; Filename: "{app}\UV-Security-Manager.exe"
Name: "{group}\Quick start"; Filename: "{app}\QUICK-START.txt"

[Run]
Filename: "{app}\UV-Security-Manager.exe"; Description: "Open UV Security Manager"; Flags: nowait postinstall skipifsilent
