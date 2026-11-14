@echo off
setlocal
cd /d "%~dp0"
py -3 -m venv .build-venv
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
".build-venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --name UV-Security-Manager app.py
if errorlevel 1 goto failed
echo.
echo Built: dist\UV-Security-Manager.exe
echo Your data stays in %%LOCALAPPDATA%%\UVSecurityManager
pause
exit /b 0
:failed
echo Build failed. Read the message above.
pause
exit /b 1
