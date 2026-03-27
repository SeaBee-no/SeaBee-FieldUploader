@echo off
setlocal

echo ============================================
echo   SeaBee FieldUploader - Setup (Windows)
echo ============================================
echo.

set "ROOT=%~dp0"
cd /d "%ROOT%"

:: Create directories
if not exist "runtime" mkdir runtime
if not exist "configs" mkdir configs

:: -------------------------------------------------------
:: Python (standalone build — includes tkinter + pip)
:: -------------------------------------------------------
if exist "runtime\python\python.exe" (
    echo [OK] Python already installed.
    goto :install_packages
)

echo [1/4] Downloading Python 3.12 (standalone^)...
echo       This is ~40 MB, please wait...
curl -L --progress-bar -o "runtime\python.tar.gz" "https://github.com/indygreg/python-build-standalone/releases/download/20241219/cpython-3.12.8+20241219-x86_64-pc-windows-msvc-install_only_stripped.tar.gz"
if errorlevel 1 (
    echo.
    echo FAILED to download Python. Check your internet connection.
    pause
    exit /b 1
)

echo       Extracting...
tar -xzf "runtime\python.tar.gz" -C "runtime"
del "runtime\python.tar.gz"

if not exist "runtime\python\python.exe" (
    echo ERROR: Python extraction failed.
    pause
    exit /b 1
)

echo [OK] Python ready (includes tkinter^).

:install_packages
echo [2/4] Installing Python packages...
"runtime\python\python.exe" -m pip install PyYAML -q --no-warn-script-location 2>nul

:: -------------------------------------------------------
:: Rclone
:: -------------------------------------------------------
if exist "runtime\rclone\rclone.exe" (
    echo [OK] Rclone already installed.
    goto :config
)

echo [3/4] Downloading rclone...
curl -L --progress-bar -o "runtime\rclone.zip" "https://downloads.rclone.org/rclone-current-windows-amd64.zip"
if errorlevel 1 (
    echo.
    echo FAILED to download rclone. Check your internet connection.
    pause
    exit /b 1
)

echo       Extracting...
mkdir "runtime\rclone-tmp" 2>nul
tar -xf "runtime\rclone.zip" -C "runtime\rclone-tmp"
mkdir "runtime\rclone" 2>nul

:: The zip contains a versioned subfolder, e.g. rclone-v1.68.2-windows-amd64/
for /d %%i in ("runtime\rclone-tmp\rclone-*") do (
    copy "%%i\rclone.exe" "runtime\rclone\rclone.exe" >nul
)
rmdir /s /q "runtime\rclone-tmp"
del "runtime\rclone.zip"

echo [OK] Rclone ready.

:: -------------------------------------------------------
:: Config files
:: -------------------------------------------------------
:config
echo.
echo Ensuring config files...

if not exist "configs\rclone.conf" (
    if exist "resources\rclone.conf.template" (
        copy "resources\rclone.conf.template" "configs\rclone.conf" >nul
        echo [NEW] configs\rclone.conf created - EDIT THIS with your S3 credentials!
    )
)

if not exist "configs\defaults.txt" (
    if exist "resources\defaults.txt" (
        copy "resources\defaults.txt" "configs\defaults.txt" >nul
    )
)

if not exist "configs\bucket.conf" (
    if exist "resources\bucket.conf.template" (
        copy "resources\bucket.conf.template" "configs\bucket.conf" >nul
    )
)

echo.
echo ============================================
echo   Setup complete!
echo.
echo   Double-click  run.bat  to start the app.
echo   Edit  configs\rclone.conf  with your
echo   S3 credentials before uploading.
echo ============================================
echo.
pause
