@echo off
setlocal
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Setup-Windows.ps1"
if errorlevel 1 (
    echo.
    echo Setup failed. Read the message above. No client records were removed.
    pause
    exit /b 1
)
echo.
echo Setup complete. Use the UV Security Manager desktop shortcut.
pause
