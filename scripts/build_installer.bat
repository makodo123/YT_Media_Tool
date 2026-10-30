@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
rem 以 Inno Setup 建立安裝程式；需先執行 scripts\build_exe.bat 產生 dist\YT_Media_Tool
rem 安裝 Inno Setup：winget install -e --id JRSoftware.InnoSetup
if not exist ".venv\Scripts\python.exe" (
    echo 請先執行 scripts\setup_windows.bat 建立開發環境。
    exit /b 1
)
set "PYTHONUTF8=1"
".venv\Scripts\python.exe" scripts\build_installer.py
exit /b %errorlevel%
