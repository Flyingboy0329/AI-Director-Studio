@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" -X utf8 -B 03_Code\check_cpu_sensor.py --read
) else (
    python -X utf8 -B 03_Code\check_cpu_sensor.py --read
)
pause
