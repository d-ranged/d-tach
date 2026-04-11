import logging

from flask import Blueprint, jsonify

logger = logging.getLogger(__name__)

bp = Blueprint("browse", __name__)


def _open_file_dialog() -> str:
    """Open a native OS file picker and return the selected path, or empty string."""
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
