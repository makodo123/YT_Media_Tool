@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0.."

rem 用法：scripts\build_exe.bat [--no-ffmpeg] [--no-deno] [--skip-tests]
set "BUNDLE_FFMPEG=1"
set "BUNDLE_DENO=1"
set "RUN_TESTS=1"
:parse
if "%~1"=="" goto parsed
if /I "%~1"=="--no-ffmpeg" set "BUNDLE_FFMPEG=0"
if /I "%~1"=="--no-deno" set "BUNDLE_DENO=0"
if /I "%~1"=="--skip-tests" set "RUN_TESTS=0"
shift
goto parse
:parsed

rem 輸出重新導向（例如 CI）時，確保 Python 以 UTF-8 輸出繁體中文
set "PYTHONUTF8=1"
set "PY=.venv\Scripts\python.exe"
if not exist "%PY%" goto novenv
set "VERSION=2.8.0"
set "DIST=dist\YT_Media_Tool"

rem 測試使用 offscreen；結束後還原原本的設定（CI 會預先設定 offscreen 供啟動測試使用）
set "ORIG_QPA=%QT_QPA_PLATFORM%"
if "%RUN_TESTS%"=="1" (
    echo === 1/5 執行測試 ===
    set "QT_QPA_PLATFORM=offscreen"
    "%PY%" -m pytest -q
    if errorlevel 1 goto fail
    set "QT_QPA_PLATFORM=%ORIG_QPA%"
)

if "%BUNDLE_FFMPEG%"=="1" (
    echo === 2/5 準備 FFmpeg（依 packaging\ffmpeg_manifest.json 驗證 SHA256）===
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\fetch_ffmpeg.ps1
    if errorlevel 1 goto fail
) else (
    echo === 2/5 不隨附 FFmpeg（程式會偵測並顯示安裝指引）===
)

echo === 3/5 PyInstaller 建置（one-folder）===
set "YTMT_BUNDLE_FFMPEG=%BUNDLE_FFMPEG%"
set "YTMT_BUNDLE_DENO=%BUNDLE_DENO%"
"%PY%" -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging\yt_media_tool.spec
if errorlevel 1 goto fail
copy /y README.md "%DIST%\README.md" >nul
copy /y THIRD_PARTY_NOTICES.md "%DIST%\THIRD_PARTY_NOTICES.md" >nul
copy /y LICENSE "%DIST%\LICENSE.txt" >nul
copy /y docs\RELEASE_NOTES.md "%DIST%\RELEASE_NOTES.md" >nul

echo === 4/5 檢查發行資料夾 ===
set "VERIFY_ARGS="
if "%BUNDLE_FFMPEG%"=="1" set "VERIFY_ARGS=%VERIFY_ARGS% --expect-ffmpeg"
if "%BUNDLE_DENO%"=="1" set "VERIFY_ARGS=%VERIFY_ARGS% --expect-deno"
"%PY%" scripts\verify_dist.py "%DIST%" %VERIFY_ARGS%
if errorlevel 1 goto fail
rem 啟動測試：使用獨立的資料目錄，不影響使用者的 AppData
set "YTMT_DATA_DIR=%CD%\build\smoke_appdata"
start "" /wait "%DIST%\YT_Media_Tool.exe" --smoke-test
if errorlevel 1 goto fail
set "YTMT_DATA_DIR="

echo === 5/5 壓縮發行檔 ===
"%PY%" scripts\make_release_zip.py "%DIST%" "dist\YT_Media_Tool-%VERSION%-win64.zip"
if errorlevel 1 goto fail
set "ZIP=dist\YT_Media_Tool-%VERSION%-win64.zip"

echo.
echo 建置完成：%DIST%\YT_Media_Tool.exe
echo 發行壓縮檔：%ZIP%
exit /b 0

:novenv
echo 找不到 .venv，請先執行 scripts\setup_windows.bat
exit /b 1

:fail
echo [失敗] 建置中止，請檢查上方訊息。
exit /b 1
