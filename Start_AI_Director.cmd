@echo off
cd /d "%~dp0"
if exist "%~dp0AI Director Studio.exe" (
    start "" "%~dp0AI Director Studio.exe"
    exit /b 0
)
python -X utf8 03_Code\app_gui.py
if errorlevel 1 pause
