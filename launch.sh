#!/usr/bin/env bash
cd "$(dirname "$0")"

if [ ! -f ".venv/bin/activate" ]; then
    echo "Virtual environment not found."
    echo "Please follow the setup instructions in README.md before running this script."
    exit 1
fi

source .venv/bin/activate
python run.py
