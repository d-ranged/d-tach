#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

# ---- Check Python is installed and is 3.11 or newer ----
if ! command -v python3 &>/dev/null; then
    echo ""
    echo "ERROR: Python 3 is not installed."
    echo ""
    echo "Please install Python 3.11 or newer:"
    echo "  macOS:  https://www.python.org/downloads/"
    echo "  Linux:  use your package manager, e.g.  sudo apt install python3"
    echo ""
    exit 1
fi

if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)"; then
    FOUND=$(python3 --version 2>&1)
    echo ""
    echo "ERROR: $FOUND found, but d-tach requires Python 3.11 or newer."
    echo "Please install Python 3.11+ from: https://www.python.org/downloads/"
    echo ""
    exit 1
fi

# ---- First-run setup if virtual environment does not exist ----
if [ ! -f ".venv/bin/activate" ]; then
    echo "First-time setup: creating virtual environment..."
    python3 -m venv .venv
    source .venv/bin/activate
    echo "Installing dependencies (this may take a few minutes)..."
    pip install -r requirements.txt
    echo "Downloading English language model..."
    python -m spacy download en_core_web_md
    echo "Downloading Dutch language model..."
    python -m spacy download nl_core_news_md
    echo ""
    echo "Setup complete. Starting d-tach..."
    echo ""
else
    source .venv/bin/activate
fi

python run.py