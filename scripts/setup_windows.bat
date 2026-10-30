@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0.."

echo === YT Media Tool V2.0：建立開發環境 ===
where py >nul 2>nul
if errorlevel 1 goto nopy
py -3.12 -c "import sys; print('Python', sys.version)"
if errorlevel 1 goto nopy

if not exist ".venv\Scripts\python.exe" (
    echo 建立虛擬環境 .venv ...
    py -3.12 -m venv .venv
    if errorlevel 1 goto fail
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto fail
".venv\Scripts\python.exe" -m pip install -r requirements-dev.txt
if errorlevel 1 goto fail

echo.
echo 完成。執行 scripts\run_dev.bat 啟動程式；執行 scripts\build_exe.bat 打包 EXE。
exit /b 0

:nopy
echo [錯誤] 找不到 Python 3.12。請先安裝：winget install -e --id Python.Python.3.12
exit /b 1

:fail
echo [錯誤] 安裝失敗，請檢查上方訊息與網路連線。
exit /b 1
