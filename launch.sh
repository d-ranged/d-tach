#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# ---- First-run setup: create venv and download language models ----
if [ ! -f ".venv/bin/python" ]; then
    if ! command -v python3 &>/dev/null; then
        echo ""
        echo "ERROR: Python 3 is not installed."
        echo ""
        echo "  macOS:  brew install python  or  https://www.python.org/downloads/"
        echo "  Linux:  sudo apt install python3 python3-venv  (or equivalent)"
        echo ""
        exit 1
    fi

    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"; then
        echo ""
        echo "ERROR: $(python3 --version 2>&1) found — d-tach requires Python 3.11 or newer."
        echo ""
        exit 1
    fi

    echo "Setting up d-tach for the first time..."
    echo ""
    python3 -m venv .venv
    echo "Installing dependencies (this may take a few minutes)..."
    .venv/bin/pip install -r requirements.txt
    if ! .venv/bin/python -c "import tkinter" 2>/dev/null; then
        echo ""
        echo "Note: tkinter not found — Browse buttons will be disabled."
        echo "To enable, run: brew install python-tk@3.x  (replace 3.x with your Python version)"
        echo ""
    fi
    echo "Downloading English language model..."
    .venv/bin/python -m spacy download en_core_web_md
    echo "Downloading Dutch language model..."
    .venv/bin/python -m spacy download nl_core_news_md
    echo ""
    echo "Setup complete - starting d-tach now."
    echo ""
fi

# ---- Sync dependencies (fast when already up to date; picks up new packages after updates) ----
echo "Checking dependencies..."
.venv/bin/python -m pip install -r requirements.txt -q
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Dependency installation failed."
    echo ""
    exit 1
fi

# ---- Start d-tach (tray app) ----
# d-tach opens the browser itself once the server is confirmed listening, on
# whichever port is configured in Settings. Waiting on a fixed delay here
# opened a dead tab whenever startup ran long or failed.
echo "Starting d-tach..."
export DTACH_OPEN_BROWSER=1
.venv/bin/python tray.py
