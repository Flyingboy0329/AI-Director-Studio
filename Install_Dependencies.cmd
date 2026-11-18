@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3.10 -m venv .venv
if not errorlevel 1 goto install
python -m venv .venv
if errorlevel 1 goto failed
:install
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Dependencies installed. Open AI Director Studio.exe.
pause
exit /b 0
:failed
echo Setup failed. See README. Python 3.10+ and internet access are required.
pause
exit /b 1
