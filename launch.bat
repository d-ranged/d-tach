@echo off
cd /d "%~dp0"

:: ---- Check Python is installed and is 3.11 or newer ----
python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python 3.11 or newer is required but was not found.
    echo.
    echo If Python is not installed:
    echo   1. Go to https://www.python.org/downloads/
    echo   2. Download and run the installer.
    echo   3. On the first screen, tick "Add Python to PATH".
    echo   4. Complete the installation, then double-click launch.bat again.
    echo.
    echo If Python IS installed but this message still appears, it may not
    echo be added to PATH. Re-run the installer and tick "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

:: ---- First-run setup if virtual environment does not exist ----
if not exist ".venv\Scripts\activate.bat" (
    echo First-time setup: creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
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