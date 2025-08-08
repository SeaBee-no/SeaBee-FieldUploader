@echo off
setlocal

REM Get absolute path of the folder this .bat is in
set "BASEDIR=%~dp0"

REM Remove trailing backslash if present
if "%BASEDIR:~-1%"=="\" set "BASEDIR=%BASEDIR:~0,-1%"

REM Define absolute paths
set "PYTHON=%BASEDIR%\resources\WPy64-31330\python\python.exe"
set "APP=%BASEDIR%\resources\app.py"

REM Run the app
"%PYTHON%" "%APP%"
