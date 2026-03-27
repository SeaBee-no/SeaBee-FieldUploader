#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

# Find the Python that setup.sh installed
if [ -f "runtime/venv/bin/python3" ]; then
    PYTHON="runtime/venv/bin/python3"
elif [ -f "runtime/python/bin/python3" ]; then
    PYTHON="runtime/python/bin/python3"
elif command -v python3 &>/dev/null; then
    PYTHON="python3"
else
    echo "Python not found. Please run setup.sh first."
    exit 1
fi

PYTHONPATH="$ROOT" exec "$PYTHON" -m app
