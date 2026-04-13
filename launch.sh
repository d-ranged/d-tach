#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

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
