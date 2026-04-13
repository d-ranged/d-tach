@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo Virtual environment not found.
    echo Please follow the setup instructions in README.md before running this script.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat
python run.py
pause
