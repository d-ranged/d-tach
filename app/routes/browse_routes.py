import logging

from flask import Blueprint, jsonify

from app.tcl_support import ensure_tcl_available, tk_dialogs_available

logger = logging.getLogger(__name__)

bp = Blueprint("browse", __name__)

# Checked once at import so browse_status() can answer without opening a dialog.
# This probes a real Tk root rather than just the import, so a Python install
# that ships tkinter without usable Tcl data files is reported as unavailable
# instead of failing at the moment the user clicks Browse.
_TKINTER_AVAILABLE = tk_dialogs_available()


def _open_file_dialog() -> str:
    """Open a native OS file picker and return the selected path, or empty string."""
    ensure_tcl_available()
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[
            ("Supported documents", "*.docx *.pdf *.md *.xlsx"),
            ("Word documents", "*.docx"),
            ("Excel files", "*.xlsx"),
            ("PDF files", "*.pdf"),
            ("Markdown files", "*.md"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return path or ""


def _open_csv_dialog() -> str:
    """Open a native OS file picker filtered to CSV files."""
    ensure_tcl_available()
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select a KEYREF CSV file",
        filetypes=[
            ("CSV files", "*.csv"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return path or ""


def _open_folder_dialog() -> str:
    """Open a native OS folder picker and return the selected path, or empty string."""
    ensure_tcl_available()
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askdirectory(title="Select a folder")
    root.destroy()
    return path or ""


@bp.route("/browse/status")
def browse_status():
    """Return whether native file/folder dialogs are available.

    Returns JSON: {"available": true} or {"available": false}.
    The frontend uses this on page load to show or hide the Browse buttons.
    """
    return jsonify({"available": _TKINTER_AVAILABLE})


@bp.route("/browse/file")
def browse_file():
    """Open a native file picker dialog and return the selected file path.

    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    Returns {"error": "...", "tkinter_unavailable": true} if tkinter is not installed.
    """
    if not _TKINTER_AVAILABLE:
        return jsonify({
            "error": "Browse buttons require tkinter, which is not installed on this system.",
            "tkinter_unavailable": True,
        })
    try:
        path = _open_file_dialog()
        return jsonify({"path": path})
    except Exception as exc:
        logger.error("File browser dialog failed: %s", exc)
        return jsonify({"error": str(exc)}), 500


@bp.route("/browse/csv")
def browse_csv():
    """Open a native file picker filtered to CSV files and return the selected path.

    Used by the Restore tab's KEYREF file input.
    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    """
    if not _TKINTER_AVAILABLE:
        return jsonify({
            "error": "Browse buttons require tkinter, which is not installed on this system.",
            "tkinter_unavailable": True,
        })
    try:
        path = _open_csv_dialog()
        return jsonify({"path": path})
    except Exception as exc:
        logger.error("CSV browser dialog failed: %s", exc)
        return jsonify({"error": str(exc)}), 500


@bp.route("/browse/folder")
def browse_folder():
    """Open a native folder picker dialog and return the selected folder path.

    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    Returns {"error": "...", "tkinter_unavailable": true} if tkinter is not installed.
    """
    if not _TKINTER_AVAILABLE:
        return jsonify({
            "error": "Browse buttons require tkinter, which is not installed on this system.",
            "tkinter_unavailable": True,
        })
    try:
        path = _open_folder_dialog()
        return jsonify({"path": path})
    except Exception as exc:
        logger.error("Folder browser dialog failed: %s", exc)
        return jsonify({"error": str(exc)}), 500
