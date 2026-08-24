@echo off
cd /d "%~dp0"

:: ---- First-run setup: create venv and download language models ----
if not exist ".venv\Scripts\python.exe" (
    echo Setting up d-tach for the first time...
    echo.

    where python >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python was not found on your PATH.
        echo Install Python 3.11 or newer from https://www.python.org/
        echo.
        pause
        exit /b 1
    )

    :: 'call' matters here: if python resolves to a .bat shim (pyenv-win, for
    :: example) a bare invocation transfers control and never comes back.
    call python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
    if errorlevel 1 (
        echo ERROR: d-tach requires Python 3.11 or newer.
        call python --version
        echo.
        pause
        exit /b 1
    )

    call python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
        echo.
        pause
        exit /b 1
    )

    echo Installing dependencies ^(this may take a few minutes^)...
    .venv\Scripts\python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Dependency installation failed.
        echo.
        pause
        exit /b 1
    )

    echo Downloading English language model...
    .venv\Scripts\python -m spacy download en_core_web_md
    echo Downloading Dutch language model...
    .venv\Scripts\python -m spacy download nl_core_news_md

    echo.
    echo Setup complete - starting d-tach now.
    echo.
)

:: ---- Sync dependencies (fast when already up to date; picks up new packages after updates) ----
echo Checking dependencies...
.venv\Scripts\python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo.
    echo ERROR: Dependency installation failed.
    echo.
    pause
    exit /b 1
)

:: ---- Start d-tach (tray app) ----
:: d-tach opens the browser itself once the server is confirmed listening, on
:: whichever port is configured in Settings. Waiting on a fixed delay here
:: opened a dead tab whenever startup ran long or failed.
echo Starting d-tach...
set DTACH_OPEN_BROWSER=1
.venv\Scripts\python tray.py
if errorlevel 1 (
    echo.
    echo d-tach exited with an error - see the message above.
    echo.
    pause
)
