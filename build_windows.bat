@echo off
setlocal
cd /d "%~dp0"

py -3 -m pip install -r requirements.txt
if errorlevel 1 exit /b 1

py -3 -m PyInstaller --noconfirm --clean --onefile --windowed --name LudoClub ludogame.py
if errorlevel 1 exit /b 1

echo Built dist\LudoClub.exe