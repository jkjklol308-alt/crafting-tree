#!/usr/bin/env bash
# Crafting Tree - launcher for Linux/macOS (the .bat file is provided for Windows)
cd "$(dirname "$0")"

PYTHON="python3"

if ! python3 -c "import PySide6" >/dev/null 2>&1; then
    echo "Creating virtual environment and installing dependencies..."
    python3 -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    PYTHON=".venv/bin/python"
fi

"$PYTHON" app.py
