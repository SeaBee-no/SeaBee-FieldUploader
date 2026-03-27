@echo off
cd /d "%~dp0"

if not exist "runtime\python\python.exe" (
    echo Python not found. Please run setup.bat first.
    pause
    exit /b 1
)

set "PYTHONPATH=%~dp0"
start "" "%~dp0runtime\python\pythonw.exe" -m app
