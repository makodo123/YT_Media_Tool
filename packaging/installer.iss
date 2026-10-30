; YT Media Tool 安裝程式（Inno Setup 6.5 以上）
;
; 由 scripts\build_installer.py 呼叫 ISCC 建置，並以 /D 傳入：
;   AppVersion  版本號（取自 src\yt_media_tool\__init__.py）
;   SourceDir   PyInstaller 產出的 one-folder 資料夾（dist\YT_Media_Tool）
;   OutputDir   安裝檔輸出位置（dist）
;
; 設計：
; - 預設「只為目前使用者」安裝（不需系統管理員權限）；可在對話框或以 /ALLUSERS 改為所有使用者（Program Files）。
; - 升級時先刪除舊版 _internal，避免殘留已移除的檔案。
; - 解除安裝時詢問是否刪除 %LOCALAPPDATA%\YT_Media_Tool（設定、佇列、歷史、日誌）；
;   靜默解除安裝時預設保留。已下載的影片一律不刪除（程式從不記錄、也不碰觸下載資料夾以外的檔案）。

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\YT_Media_Tool"
#endif
#ifndef OutputDir
  #define OutputDir "..\dist"
#endif

#define AppName "YT Media Tool"
#define AppExeName "YT_Media_Tool.exe"
#define AppDataFolder "YT_Media_Tool"

; 優先使用 Inno Setup 內建的繁體中文語系檔，舊版沒有時改用專案中的副本
#if FileExists(AddBackslash(CompilerPath) + "Languages\ChineseTraditional.isl")
  #define ChineseMessages "compiler:Languages\ChineseTraditional.isl"
#else
  #define ChineseMessages "ChineseTraditional.isl"
#endif

[Setup]
AppId={{8C2F6B1E-5D3A-4E7B-9A1C-2F4D6E8B0A13}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=makodo123
AppPublisherURL=https://github.com/makodo123/YT_Media_Tool
AppSupportURL=https://github.com/makodo123/YT_Media_Tool/issues
AppUpdatesURL=https://github.com/makodo123/YT_Media_Tool/releases
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename=YT_Media_Tool-{#AppVersion}-win64-setup
SetupIconFile=..\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
InfoBeforeFile=installer_notice.txt
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
AppMutex=YTMediaTool_AppMutex
SetupLogging=yes
VersionInfoVersion={#AppVersion}
VersionInfoProductName={#AppName}
VersionInfoDescription={#AppName} 安裝程式

[Languages]
Name: "chinesetraditional"; MessagesFile: "{#ChineseMessages}"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; 升級時清除舊版的程式元件（不影響使用者資料，資料在 %LOCALAPPDATA%）
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: String;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\{#AppDataFolder}');
    if DirExists(DataDir) then
    begin
      if SuppressibleMsgBox(
           '是否一併刪除程式設定、下載佇列、歷史紀錄與日誌？' + #13#10 +
           '（' + DataDir + '）' + #13#10#13#10 +
           '已下載的影片與音樂不會被刪除。',
           mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDNO) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
