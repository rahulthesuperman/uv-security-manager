@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 app.py
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo Python 3.12 or newer is required. Install from https://www.python.org/downloads/windows/
        echo Select Add Python to PATH during installation, then run this file again.
        pause
        exit /b 1
    )
    python app.py
)
if errorlevel 1 pause
