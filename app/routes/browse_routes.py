import logging
import os
import sys

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("browse", __name__)

_TCL_FIXED = False


def _ensure_tcl_available() -> None:
    """Set TCL_LIBRARY for pyenv-win installations where Tcl path isn't auto-detected.

    On a standard Windows Python install this is a no-op.
    On macOS and Linux tkinter finds Tcl without any env var help, so the
    platform guard makes this function a no-op on those platforms too.
    """
    global _TCL_FIXED
    if _TCL_FIXED or sys.platform != "win32" or os.environ.get("TCL_LIBRARY"):
        return
    python_dir = sys.base_prefix  # base install, not the venv
    tcl_dir = os.path.join(python_dir, "tcl", "tcl8.6")
    tk_dir = os.path.join(python_dir, "tcl", "tk8.6")
    if os.path.isdir(tcl_dir):
        os.environ["TCL_LIBRARY"] = tcl_dir
    if os.path.isdir(tk_dir):
        os.environ["TK_LIBRARY"] = tk_dir
    _TCL_FIXED = True


def _open_file_dialog() -> str:
    """Open a native OS file picker and return the selected path, or empty string."""
    _ensure_tcl_available()
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askopenfilename(
        title="Select a file",
        filetypes=[
            ("Supported documents", "*.docx *.pdf"),
            ("Word documents", "*.docx"),
            ("PDF files", "*.pdf"),
            ("All files", "*.*"),
        ],
    )
    root.destroy()
    return path or ""


def _open_folder_dialog() -> str:
    """Open a native OS folder picker and return the selected path, or empty string."""
    _ensure_tcl_available()
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    path = filedialog.askdirectory(title="Select a folder")
    root.destroy()
    return path or ""


@bp.route("/browse/file")
def browse_file():
    """Open a native file picker dialog and return the selected file path.

    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    Returns {"error": "..."} if tkinter is unavailable.
    """
    try:
        path = _open_file_dialog()
        return jsonify({"path": path})
    except Exception as exc:
        logger.error("File browser dialog failed: %s", exc)
        return jsonify({"error": str(exc)}), 500


@bp.route("/browse/folder")
def browse_folder():
    """Open a native folder picker dialog and return the selected folder path.

    Returns JSON: {"path": "<selected path>"} or {"path": ""} if cancelled.
    Returns {"error": "..."} if tkinter is unavailable.
    """
    try:
        path = _open_folder_dialog()
        return jsonify({"path": path})
    except Exception as exc:
        logger.error("Folder browser dialog failed: %s", exc)
        return jsonify({"error": str(exc)}), 500
