@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo 請先執行 scripts\setup_windows.bat 建立開發環境。
    exit /b 1
)
".venv\Scripts\python.exe" main.py %*
