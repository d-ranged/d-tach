#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# ---- First-run setup: create venv and install dependencies ----
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
    echo "Setup complete."
    echo ""
fi

# ---- Open browser after Flask has had time to bind ----
(sleep 3 && {
    if command -v open &>/dev/null; then
        open http://localhost:5000
    elif command -v xdg-open &>/dev/null; then
        xdg-open http://localhost:5000
    fi
}) &

# ---- Start Flask ----
echo "Starting d-tach..."
.venv/bin/python run.py
