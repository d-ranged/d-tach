"""Native file, folder and yes/no dialogs, safe on every platform d-tach runs on.

The Browse buttons open dialogs from a Flask request thread. Windows and Linux
allow a Tk window on any thread as long as it is created and used there. macOS
only allows windows on the main thread, and the main thread belongs to the
tray icon. So on macOS each dialog runs in a short-lived child process: d-tach
starts itself again with ``--dialog <kind> <result file>``, the child opens the
dialog on its own main thread, writes the answer to the result file and exits.

Frozen, the child is the d-tach executable itself. From source it is
``python tray.py``. Either way ``tray.py`` hands the arguments to
:func:`run_dialog_child` before it starts anything else.
"""
import json
import logging
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Final, Optional

from app.app_paths import bundle_dir, is_frozen
from app.tcl_support import ensure_tcl_available

logger = logging.getLogger(__name__)

DIALOG_FLAG: Final[str] = "--dialog"
ENTRY_SCRIPT: Final[str] = "tray.py"

KIND_FILE: Final[str] = "file"
KIND_CSV: Final[str] = "csv"
KIND_FOLDER: Final[str] = "folder"
KIND_YES_NO: Final[str] = "yes_no"
KIND_PROBE: Final[str] = "probe"

DOCUMENT_FILETYPES: Final[list[tuple[str, str]]] = [
    ("Supported documents", "*.docx *.pdf *.md *.xlsx"),
    ("Word documents", "*.docx"),
    ("Excel files", "*.xlsx"),
    ("PDF files", "*.pdf"),
    ("Markdown files", "*.md"),
    ("All files", "*.*"),
]
CSV_FILETYPES: Final[list[tuple[str, str]]] = [
    ("CSV files", "*.csv"),
    ("All files", "*.*"),
]


class DialogError(RuntimeError):
    """Raised when a dialog could not be shown."""


# ----------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------


def pick_file() -> str:
    """Ask for a document to open. Returns the path, or an empty string if cancelled."""
    return str(_run(KIND_FILE) or "")


def pick_csv() -> str:
    """Ask for a KEYREF CSV file. Returns the path, or an empty string if cancelled."""
    return str(_run(KIND_CSV) or "")


def pick_folder() -> str:
    """Ask for a folder. Returns the path, or an empty string if cancelled."""
    return str(_run(KIND_FOLDER) or "")


def ask_yes_no(title: str, message: str) -> bool:
    """Ask a yes/no question. Returns True for yes."""
    return bool(_run(KIND_YES_NO, title, message))


def dialogs_available() -> bool:
    """Return True if a native dialog can actually be opened on this machine.

    Stronger than ``import tkinter``: it builds and tears down a real Tk root,
    which is where a broken Tcl installation shows up. On macOS the check runs
    in a child process, like the dialogs themselves.
    """
    try:
        return bool(_run(KIND_PROBE))
    except Exception as exc:  # noqa: BLE001 - any failure means "no dialogs"
        logger.info("Native dialogs unavailable: %s: %s", type(exc).__name__, exc)
        return False


def needs_child_process(platform: Optional[str] = None) -> bool:
    """Return True where dialogs must not open on a background thread (macOS)."""
    return (platform or sys.platform) == "darwin"


def child_command(kind: str, result_file: Path, *args: str) -> list[str]:
    """Return the command that runs one dialog in a child process."""
    if is_frozen():
        launcher = [sys.executable]
    else:
        launcher = [sys.executable, str(bundle_dir() / ENTRY_SCRIPT)]
    return [*launcher, DIALOG_FLAG, kind, str(result_file), *args]


def run_dialog_child(argv: list[str]) -> int:
    """Child-process side: show one dialog and write its answer to the result file.

    ``argv`` is everything after ``--dialog``: kind, result file, then the
    dialog's own arguments. Returns the process exit code.
    """
    if len(argv) < 2:
        return 2
    kind, result_file, args = argv[0], Path(argv[1]), argv[2:]
    try:
        payload = {"result": _run_in_process(kind, *args)}
    except Exception as exc:  # noqa: BLE001 - reported to the parent, not raised here
        payload = {"error": f"{type(exc).__name__}: {exc}"}
    result_file.write_text(json.dumps(payload), encoding="utf-8")
    return 0


# ----------------------------------------------------------------------
# Dispatch
# ----------------------------------------------------------------------


def _run(kind: str, *args: str) -> object:
    """Show one dialog in this process or a child, as the platform requires."""
    if needs_child_process():
        return _run_in_child(kind, *args)
    return _run_in_process(kind, *args)


def _run_in_child(kind: str, *args: str) -> object:
    """Run one dialog in a child process and return its answer."""
    with tempfile.TemporaryDirectory(prefix="d-tach-dialog-") as tmp:
        result_file = Path(tmp) / "result.json"
        completed = subprocess.run(child_command(kind, result_file, *args), capture_output=True, text=True)
        if not result_file.exists():
            raise DialogError(
                f"The {kind} dialog exited with code {completed.returncode} and no answer. "
                f"{(completed.stderr or '').strip()[-300:]}"
            )
        payload = json.loads(result_file.read_text(encoding="utf-8"))
    if "error" in payload:
        raise DialogError(payload["error"])
    return payload.get("result")


def _run_in_process(kind: str, *args: str) -> object:
    """Run one dialog on the calling thread."""
    handlers: dict[str, Callable[..., object]] = {
        KIND_FILE: _tk_pick_file,
        KIND_CSV: _tk_pick_csv,
        KIND_FOLDER: _tk_pick_folder,
        KIND_YES_NO: _tk_ask_yes_no,
        KIND_PROBE: _tk_probe,
    }
    handler = handlers.get(kind)
    if handler is None:
        raise ValueError(f"Unknown dialog kind: {kind!r}")
    return handler(*args)


# ----------------------------------------------------------------------
# Tk implementations
# ----------------------------------------------------------------------


def _tk_root():
    """Create a hidden, topmost Tk root for one dialog."""
    ensure_tcl_available()
    import tkinter as tk

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    # A child process starts behind the browser on macOS; pull it forward.
    root.lift()
    root.focus_force()
    return root


def _tk_pick_file() -> str:
    """Open a native file picker for supported documents."""
    from tkinter import filedialog

    root = _tk_root()
    try:
        return filedialog.askopenfilename(title="Select a file", filetypes=DOCUMENT_FILETYPES) or ""
    finally:
        root.destroy()


def _tk_pick_csv() -> str:
    """Open a native file picker filtered to CSV files."""
    from tkinter import filedialog

    root = _tk_root()
    try:
        return filedialog.askopenfilename(title="Select a KEYREF CSV file", filetypes=CSV_FILETYPES) or ""
    finally:
        root.destroy()


def _tk_pick_folder() -> str:
    """Open a native folder picker."""
    from tkinter import filedialog

    root = _tk_root()
    try:
        return filedialog.askdirectory(title="Select a folder") or ""
    finally:
        root.destroy()


def _tk_ask_yes_no(title: str, message: str) -> bool:
    """Open a native yes/no message box."""
    from tkinter import messagebox

    root = _tk_root()
    try:
        return bool(messagebox.askyesno(title, message))
    finally:
        root.destroy()


def _tk_probe() -> bool:
    """Build and destroy a Tk root to prove dialogs can open."""
    ensure_tcl_available()
    import tkinter as tk

    root = tk.Tk()
    root.destroy()
    return True
