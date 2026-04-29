@echo off
cd /d "%~dp0"

:: ---- First-run setup: create venv and download language models ----
if not exist ".venv\Scripts\python.exe" (
    echo Setting up d-tach for the first time...
    echo.
    python -m venv .venv
    if errorlevel 1 (
        echo.
        echo ERROR: Could not create virtual environment.
        echo Make sure Python 3.11 or newer is installed from https://www.python.org/
        echo.
        pause
        exit /b 1
    )
    echo Installing dependencies ^(this may take a few minutes^)...
    .venv\Scripts\pip install -r requirements.txt
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
    echo Setup complete.
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

:: ---- Start Flask and open browser after it has had time to bind ----
echo Starting d-tach...
start /b cmd /c "timeout /t 3 /nobreak >nul && start http://localhost:5000"
.venv\Scripts\python run.py
pause
