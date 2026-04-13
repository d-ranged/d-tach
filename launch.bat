@echo off
cd /d "%~dp0"

if not exist ".venv\Scripts\activate.bat" (
    echo First-time setup: creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
        echo Make sure Python 3.11 or newer is installed and added to PATH.
        echo Download Python from: https://www.python.org/downloads/
        echo During installation, tick "Add Python to PATH".
        pause
        exit /b 1
    )
    call .venv\Scripts\activate.bat
    echo Installing dependencies ^(this may take a few minutes^)...
    pip install -r requirements.txt
    echo Downloading English language model...
    python -m spacy download en_core_web_md
    echo Downloading Dutch language model...
    python -m spacy download nl_core_news_md
    echo.
    echo Setup complete. Starting d-tach...
    echo.
) else (
    call .venv\Scripts\activate.bat
)

python run.py
pause
