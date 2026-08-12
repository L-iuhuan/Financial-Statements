; Inno Setup 安装脚本: 财务报表勾稽校验系统
; 编译: 需要 Inno Setup 6 (https://jrsoftware.org/isdl.php)
;        ISCC.exe installer.iss
; 产物: installer_output\财务报表勾稽校验系统_Setup_0.1.0.exe

#define MyAppName "财务报表勾稽校验系统"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "FSA"
#define MyAppExeName "fsa.exe"
#define MyAppId "{{8F3A2B1C-4D5E-4F6A-9B8C-1D2E3F4A5B6C}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; 允许非管理员安装到用户目录
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=installer_output
OutputBaseFilename=财务报表勾稽校验系统_Setup_{#MyAppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
; 中文界面
ShowLanguageDialog=no

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; 打包 PyInstaller onedir 产物 (dist\fsa 下全部内容, 含 _internal)
Source: "dist\fsa\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 规则库 JSON 随 exe 一起 (已在 dist\fsa\_internal 中, 上一行已覆盖)

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent
