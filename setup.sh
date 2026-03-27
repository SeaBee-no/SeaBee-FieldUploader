#!/usr/bin/env bash
set -euo pipefail

echo "============================================"
echo "  SeaBee FieldUploader - Setup"
echo "============================================"
echo

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

mkdir -p runtime configs

# -----------------------------------------------------------
# Python
# -----------------------------------------------------------
NEED_PORTABLE=false

if command -v python3 &>/dev/null; then
    if python3 -c "import tkinter" 2>/dev/null; then
        echo "[OK] System Python with tkinter found."
    else
        echo "[!]  System Python found but tkinter is missing."
        NEED_PORTABLE=true
    fi
else
    echo "[!]  python3 not found."
    NEED_PORTABLE=true
fi

if [ -f "runtime/python/bin/python3" ]; then
    echo "[OK] Portable Python already installed."
    PYTHON="$ROOT/runtime/python/bin/python3"
elif [ "$NEED_PORTABLE" = true ]; then
    echo "[1/4] Downloading portable Python 3.12 (includes tkinter)..."

    ARCH="$(uname -m)"
    OS="$(uname -s)"

    case "${OS}-${ARCH}" in
        Linux-x86_64)  PY_SUFFIX="x86_64-unknown-linux-gnu" ;;
        Linux-aarch64) PY_SUFFIX="aarch64-unknown-linux-gnu" ;;
        Darwin-x86_64) PY_SUFFIX="x86_64-apple-darwin" ;;
        Darwin-arm64)  PY_SUFFIX="aarch64-apple-darwin" ;;
        *)
            echo "ERROR: Unsupported platform ${OS}-${ARCH}."
            echo "Install Python 3.10+ with tkinter manually."
            exit 1
            ;;
    esac

    PY_URL="https://github.com/indygreg/python-build-standalone/releases/download/20241219/cpython-3.12.8+20241219-${PY_SUFFIX}-install_only_stripped.tar.gz"

    curl -L --progress-bar -o "runtime/python.tar.gz" "$PY_URL"
    echo "      Extracting..."
    tar -xzf "runtime/python.tar.gz" -C "runtime/"
    rm "runtime/python.tar.gz"
    echo "[OK] Portable Python installed."
    PYTHON="$ROOT/runtime/python/bin/python3"
else
    # System Python is fine — create a venv so pip install doesn't need --user
    if [ ! -d "runtime/venv" ]; then
        echo "[2/4] Creating virtual environment..."
        python3 -m venv runtime/venv
    fi
    PYTHON="$ROOT/runtime/venv/bin/python3"
fi

# -----------------------------------------------------------
# Python packages
# -----------------------------------------------------------
echo "[3/4] Installing Python packages..."
"$PYTHON" -m pip install PyYAML -q 2>/dev/null || "$PYTHON" -m pip install PyYAML -q --break-system-packages 2>/dev/null || true

# -----------------------------------------------------------
# Rclone
# -----------------------------------------------------------
if [ -f "runtime/rclone/rclone" ]; then
    echo "[OK] Rclone already installed."
elif command -v rclone &>/dev/null; then
    echo "[OK] System rclone found on PATH."
else
    echo "[4/4] Downloading rclone..."

    ARCH="$(uname -m)"
    OS="$(uname -s)"

    case "${OS}-${ARCH}" in
        Linux-x86_64)   RCLONE_URL="https://downloads.rclone.org/rclone-current-linux-amd64.zip" ;;
        Linux-aarch64)  RCLONE_URL="https://downloads.rclone.org/rclone-current-linux-arm64.zip" ;;
        Darwin-x86_64)  RCLONE_URL="https://downloads.rclone.org/rclone-current-osx-amd64.zip" ;;
        Darwin-arm64)   RCLONE_URL="https://downloads.rclone.org/rclone-current-osx-arm64.zip" ;;
        *)
            echo "WARNING: Unknown platform ${OS}-${ARCH}. Install rclone manually."
            RCLONE_URL=""
            ;;
    esac

    if [ -n "$RCLONE_URL" ]; then
        curl -L --progress-bar -o "runtime/rclone.zip" "$RCLONE_URL"
        echo "      Extracting..."
        mkdir -p "runtime/rclone-tmp"
        unzip -qo "runtime/rclone.zip" -d "runtime/rclone-tmp"
        mkdir -p "runtime/rclone"
        cp runtime/rclone-tmp/rclone-*/rclone "runtime/rclone/rclone"
        chmod +x "runtime/rclone/rclone"
        rm -rf "runtime/rclone-tmp" "runtime/rclone.zip"
        echo "[OK] Rclone ready."
    fi
fi

# -----------------------------------------------------------
# Config files
# -----------------------------------------------------------
echo
echo "Ensuring config files..."

if [ ! -f "configs/rclone.conf" ] && [ -f "resources/rclone.conf.template" ]; then
    cp "resources/rclone.conf.template" "configs/rclone.conf"
    echo "[NEW] configs/rclone.conf created — EDIT THIS with your S3 credentials!"
fi

if [ ! -f "configs/defaults.txt" ] && [ -f "resources/defaults.txt" ]; then
    cp "resources/defaults.txt" "configs/defaults.txt"
fi

if [ ! -f "configs/bucket.conf" ] && [ -f "resources/bucket.conf.template" ]; then
    cp "resources/bucket.conf.template" "configs/bucket.conf"
fi

echo
echo "============================================"
echo "  Setup complete!"
echo
echo "  Run the app with:  ./run.sh"
echo "  Edit configs/rclone.conf with your"
echo "  S3 credentials before uploading."
echo "============================================"
