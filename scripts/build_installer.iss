; ==============================================================================
; Inno Setup Script - 财务报表勾稽关系自动校验系统
; ==============================================================================
; 构建步骤:
;   1. PyInstaller 打包: pyinstaller --noconfirm --onedir --windowed src/fsa/main.py
;   2. Inno Setup 编译: iscc scripts\build_installer.iss
;   3. 输出: dist\FSASetup_v{version}_x64.exe
;
; 静默安装 (自动更新使用):
;   FSASetup_v{version}_x64.exe /SILENT /NOCANCEL /NORESTART
; ==============================================================================

#define MyAppName          "财务报表勾稽校验系统"
#define MyAppNameEn        "Financial Statement Auditor"
#define MyAppVersion       "0.1.0"
#define MyAppPublisher     "FSA Team"
#define MyAppExeName       "fsa.exe"
#define MyAppURL           "https://github.com/L-iuhuan/Financial-Statements"

; PyInstaller --onedir 输出目录
#define PyInstallerOutput   "..\dist\fsa"

[Setup]
; 基本信息
AppId={{FSA-2026-08-07-GLOBAL-ID}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; 安装目录 (用户可自定义)
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; 安装包输出
OutputDir=..\dist\installer
OutputBaseFilename=FSASetup_v{#MyAppVersion}_x64

; 压缩
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4

; 架构
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; 权限 (允许普通用户安装到自己的目录, 或管理员安装到 Program Files)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; 界面
SetupIconFile=..\resources\icons\app.ico
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

; 卸载
UninstallDisplayName={#MyAppName}

; 版本信息
VersionInfoVersion={#MyAppVersion}.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} 安装程序
VersionInfoProductName={#MyAppName}

[Languages]
Name: "chinesesimp"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"; GroupDescription: "附加图标:"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "创建快速启动栏图标"; GroupDescription: "附加图标:"; Flags: checkedonce; OnlyBelowVersion: 6.1

[Files]
; PyInstaller --onedir 输出的全部文件
Source: "{#PyInstallerOutput}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; 开始菜单
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\卸载 {#MyAppName}"; Filename: "{uninstallexe}"

; 桌面快捷方式
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

; 快速启动
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; 安装完成后启动应用
Filename: "{app}\{#MyAppExeName}"; Description: "立即启动 {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 清理用户数据 (可选: 保留用户配置)
; Type: filesandordirs; Name: "{userappdata}\FSA"

[Code]
function GetUninstallString(): String;
var
  sUnInstPath: String;
  sUnInstallString: String;
begin
  sUnInstPath := 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#emit SetupSetting("AppId")}';
  sUnInstallString := '';
  if not RegQueryStringValue(HKLM, sUnInstPath, 'UninstallString', sUnInstallString) then
    RegQueryStringValue(HKCU, sUnInstPath, 'UninstallString', sUnInstallString);
  Result := sUnInstallString;
end;

function IsUpgrade(): Boolean;
begin
  Result := (GetUninstallString() <> '');
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  if IsUpgrade() then
  begin
    if PageID = wpSelectDir then
      Result := True;
  end;
end;

function InitializeSetup(): Boolean;
var
  V: Integer;
  iResultCode: Integer;
  sUnInstallString: String;
begin
  Result := True;
  if IsUpgrade() then
  begin
    sUnInstallString := GetUninstallString();
    if sUnInstallString <> '' then
    begin
      sUnInstallString := RemoveQuotes(sUnInstallString);
      if Exec(ExpandConstant(sUnInstallString), '/SILENT /NORESTART /SUPPRESSMSGBOXES', '', SW_HIDE, ewWaitUntilTerminated, iResultCode) then
      begin
        // 旧版本卸载成功
      end
      else
      begin
        // 卸载失败, 但允许继续安装
        Result := True;
      end;
      Sleep(1000); // 等待文件释放
    end;
  end;
end;
