; Inno Setup 6 Script
; Fluent Media Player - Professional Windows Desktop Packaging

#define MyAppName "Fluent Media Player"
#define MyAppVersion "2.0.0"
#define MyAppExeName "FluentMediaPlayer.exe"
#define MyAppAssocKey "FluentMediaPlayer.Video"
#define MyOutputDir "release\installer"
#define MyOutputBaseFilename "FluentMediaPlayer-Setup"
#define MySourceDir "dist\FluentMediaPlayer"

[Setup]
; Application Identity
AppId={{9F4C2855-9F79-4B39-A8D0-E1D42DE1D5F3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=no

; Visuals & Branding
SetupIconFile=assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
WizardStyle=modern
SolidCompression=yes
Compression=lzma2/fast

; Privileges & Installation Mode
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog commandline
OutputDir={#MyOutputDir}
OutputBaseFilename={#MyOutputBaseFilename}
ArchitecturesInstallIn64BitMode=x64compatible

; Update & Uninstallation Behavior
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#MySourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autoprograms}\{#MyAppName}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#MyAppExeName}"

[Registry]
; 1. Đăng ký Application trong Windows Classes
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"",0"; Flags: uninsdeletekey

; SupportedTypes
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mp4"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mkv"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".avi"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".mov"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".flv"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".wmv"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".webm"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".m4v"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\Applications\{#MyAppExeName}\SupportedTypes"; ValueType: string; ValueName: ".ts"; ValueData: ""; Flags: uninsdeletevalue

; 2. Đăng ký ProgID: FluentMediaPlayer.Video
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}"; ValueType: string; ValueName: ""; ValueData: "Video File"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"",0"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\{#MyAppAssocKey}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" ""%1"""; Flags: uninsdeletekey

; 3. Đăng ký Capabilities cho Windows Default Programs
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "{#MyAppName}"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Fluent Media Player - Modern Windows Media Player"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mp4"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mkv"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".avi"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".mov"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".flv"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".wmv"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".webm"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".m4v"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\{#MyAppName}\Capabilities\FileAssociations"; ValueType: string; ValueName: ".ts"; ValueData: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "FluentMediaPlayer"; ValueData: "Software\{#MyAppName}\Capabilities"; Flags: uninsdeletevalue

; 4. Đăng ký OpenWithProgids (không ghi đè mặc định)
Root: HKA; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.avi\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mov\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.flv\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.wmv\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.webm\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.m4v\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.ts\OpenWithProgids"; ValueType: none; ValueName: "{#MyAppAssocKey}"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
// Bảo tồn dữ liệu người dùng (%APPDATA%\FluentMediaPlayer) trừ khi người dùng chủ động chọn xoá
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{userappdata}\FluentMediaPlayer');
    if DirExists(DataDir) and (not UninstallSilent) then
    begin
      if MsgBox('Do you want to delete your playback history and thumbnail cache?' + #13#10 + DataDir, mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      begin
        DelTree(DataDir, True, True, True);
      end;
    end;
  end;
end;
