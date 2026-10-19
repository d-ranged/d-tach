"""Where d-tach keeps its files, from source and as a frozen (PyInstaller) build.

Two kinds of location:

- The bundle: code, templates, static files and word lists. From source this
  is the project root; frozen it is PyInstaller's unpack folder
  (``sys._MEIPASS``, the ``_internal`` folder of a onedir build). Read-only in
  practice, and replaced by every update.
- The per-user data folder: settings (with the AI token and hashing secret),
  downloaded language models and the log file. Survives replacing the app.

Settings used to live next to the code as ``user_settings.json``. An existing
file there is copied to the per-user folder once, the first time it is missing.
"""
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

APP_DIR_NAME: Final[str] = "d-tach"
DATA_DIR_ENV: Final[str] = "DTACH_DATA_DIR"
SETTINGS_FILENAME: Final[str] = "user_settings.json"
MODELS_DIRNAME: Final[str] = "models"
LOGS_DIRNAME: Final[str] = "logs"
LOG_FILENAME: Final[str] = "d-tach.log"

_PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parent.parent


def is_frozen() -> bool:
    """Return True when running from a PyInstaller build rather than from source."""
    return bool(getattr(sys, "frozen", False))


def bundle_dir() -> Path:
    """Return the folder holding the code, templates, static files and data files."""
    if is_frozen():
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return _PROJECT_ROOT


def user_data_dir() -> Path:
    """Return the per-user folder for settings, models and logs.

    Windows ``%LOCALAPPDATA%\\d-tach``, macOS ``~/Library/Application Support/d-tach``,
    elsewhere ``$XDG_DATA_HOME/d-tach``. ``DTACH_DATA_DIR`` overrides all three,
    for tests and for running a second copy with its own settings.
    """
    override = os.environ.get(DATA_DIR_ENV)
    if override:
        return Path(override)
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
    return base / APP_DIR_NAME


def settings_path() -> Path:
    """Return the per-user settings file path."""
    return user_data_dir() / SETTINGS_FILENAME


def legacy_settings_path() -> Path:
    """Return where settings lived before v1.4.0: next to the code."""
    return bundle_dir() / SETTINGS_FILENAME


def models_dir() -> Path:
    """Return the per-user folder that downloaded language models are unpacked into."""
    return user_data_dir() / MODELS_DIRNAME


def log_path() -> Path:
    """Return the per-user log file path."""
    return user_data_dir() / LOGS_DIRNAME / LOG_FILENAME


def resolve_settings_path() -> Path:
    """Return the settings file to use, carrying a pre-v1.4.0 file over once.

    When the per-user file is missing and a legacy file exists, the legacy file
    is copied (not moved, so going back to an older version still finds it).
    If the copy fails the legacy file is used where it is, so the AI token and
    hashing secret are never silently replaced by defaults.
    """
    target = settings_path()
    legacy = legacy_settings_path()
    if target.exists() or not legacy.exists():
        return target
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(legacy, target)
    except OSError as exc:
        logger.error("Could not copy settings from %s to %s: %s. Using %s.", legacy, target, exc, legacy)
        return legacy
    logger.info("Carried settings over from %s to %s.", legacy, target)
    return target
