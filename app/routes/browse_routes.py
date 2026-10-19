import logging
from functools import lru_cache
from typing import Callable

from flask import Blueprint, jsonify

from app import native_dialogs

logger = logging.getLogger(__name__)

bp = Blueprint("browse", __name__)

_UNAVAILABLE_MESSAGE = "Browse buttons require tkinter, which is not installed on this system."


@lru_cache(maxsize=1)
def _dialogs_available() -> bool:
    """Check once, on first use, whether native dialogs can open.

    This probes a real Tk root rather than just the import, so a Python install
    that ships tkinter without usable Tcl data files is reported as unavailable
    instead of failing at the moment the user clicks Browse. It runs on first
    use, not at import, because on macOS the probe starts a child process.
    """
    available = native_dialogs.dialogs_available()
    logger.info("Native dialogs available: %s", available)
    return available


def _browse(open_dialog: Callable[[], str], label: str):
    """Run one Browse dialog and return the JSON response for it."""
    if not _dialogs_available():
        return jsonify({"error": _UNAVAILABLE_MESSAGE, "tkinter_unavailable": True})
    try:
        return jsonify({"path": open_dialog()})
    except Exception as exc:
        logger.error("%s browser dialog failed: %s", label, exc)
        return jsonify({"error": str(exc)}), 500


@bp.route("/browse/status")
def browse_status():
    """Return whether native file/folder dialogs are available.

    Returns JSON: {"available": true} or {"available": false}.
    The frontend uses this on page load to show or hide the Browse buttons.
    """
    return jsonify({"available": _dialogs_available()})


@bp.route("/browse/file")
def browse_file():
    """Open a native file picker dialog and return the selected file path.

    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    Returns {"error": "...", "tkinter_unavailable": true} if tkinter is not installed.
    """
    return _browse(native_dialogs.pick_file, "File")


@bp.route("/browse/csv")
def browse_csv():
    """Open a native file picker filtered to CSV files and return the selected path.

    Used by the Restore tab's KEYREF file input.
    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    """
    return _browse(native_dialogs.pick_csv, "CSV")


@bp.route("/browse/folder")
def browse_folder():
    """Open a native folder picker dialog and return the selected folder path.

    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    Returns {"error": "...", "tkinter_unavailable": true} if tkinter is not installed.
    """
    return _browse(native_dialogs.pick_folder, "Folder")
