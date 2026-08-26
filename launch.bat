@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" goto :sync_deps

REM ---- First-run setup: create venv and download language models ----
REM Flow uses goto labels rather than parenthesised if-blocks on purpose.
REM cmd.exe parses a whole block before running it, so a :: comment or a
REM stray parenthesis inside one breaks the script in ways that are hard to read.
echo Setting up d-tach for the first time...
echo.

where python >nul 2>&1
if errorlevel 1 goto :no_python

REM Use 'call' for python: if it resolves to a .bat shim, as pyenv-win installs
REM do, a bare invocation transfers control and never returns to this script.
call python -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if errorlevel 1 goto :old_python

call python -m venv .venv
if errorlevel 1 goto :venv_failed

echo Installing dependencies, this may take a few minutes...
.venv\Scripts\python -m pip install -r requirements.txt
if errorlevel 1 goto :deps_failed

echo Downloading English language model...
.venv\Scripts\python -m spacy download en_core_web_md
echo Downloading Dutch language model...
.venv\Scripts\python -m spacy download nl_core_news_md

echo.
echo Setup complete - starting d-tach now.
echo.

:sync_deps
REM ---- Sync dependencies: fast when already up to date, picks up new packages ----
echo Checking dependencies...
.venv\Scripts\python -m pip install -r requirements.txt -q
if errorlevel 1 goto :deps_failed

REM ---- Start d-tach (tray app) ----
REM d-tach opens the browser itself once the server is confirmed listening, on
REM whichever port is configured in Settings. Waiting on a fixed delay here
REM opened a dead tab whenever startup ran long or failed.
echo Starting d-tach...
set DTACH_OPEN_BROWSER=1
.venv\Scripts\python tray.py
if errorlevel 1 goto :app_failed
goto :end

:no_python
echo.
echo ERROR: Python was not found on your PATH.
echo Install Python 3.11 or newer from https://www.python.org/
echo.
pause
exit /b 1

:old_python
echo.
echo ERROR: d-tach requires Python 3.11 or newer. Found:
call python --version
echo.
pause
exit /b 1

:venv_failed
echo.
echo ERROR: Could not create the virtual environment.
echo.
pause
exit /b 1

:deps_failed
echo.
echo ERROR: Dependency installation failed.
echo.
pause
exit /b 1

:app_failed
echo.
echo d-tach exited with an error - see the message above.
echo.
pause
exit /b 1

:end
