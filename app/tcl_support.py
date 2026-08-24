"""Tcl/Tk discovery support for Python installs that don't set it up themselves.

Some Windows Python distributions — pyenv-win in particular — ship the Tcl/Tk
data files under ``<base_prefix>/tcl`` but don't tell the Tk runtime where to
look. ``import tkinter`` then succeeds while the first ``tk.Tk()`` raises
``TclError: Can't find a usable init.tcl``.

Every part of d-tach that opens a native dialog goes through
:func:`ensure_tcl_available` first so the failure never reaches the user.
"""
import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_TCL_FIXED = False


def ensure_tcl_available() -> None:
    """Point TCL_LIBRARY/TK_LIBRARY at the bundled Tcl data files if unset.

    A no-op on non-Windows platforms (macOS and Linux resolve Tcl without help),
    when the variables are already set, and on standard Windows installs that
    already find Tcl on their own. Safe to call repeatedly — the work happens once.
    """
    global _TCL_FIXED
    if _TCL_FIXED or sys.platform != "win32":
        return
    _TCL_FIXED = True

    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    # sys.base_prefix is the real install; inside a venv sys.prefix is the venv,
    # which never carries the tcl/ directory.
    tcl_root = Path(sys.base_prefix) / "tcl"
    if not tcl_root.is_dir():
        logger.debug("No tcl directory under %s — leaving Tk to find its own path.", tcl_root)
        return

    # Match whatever Tcl version this Python shipped rather than assuming 8.6.
    for var, prefix in (("TCL_LIBRARY", "tcl"), ("TK_LIBRARY", "tk")):
        if os.environ.get(var):
            continue
        candidates = sorted(
            d for d in tcl_root.iterdir()
            if d.is_dir() and d.name.startswith(prefix) and d.name[len(prefix):len(prefix) + 1].isdigit()
        )
        if candidates:
            os.environ[var] = str(candidates[-1])
            logger.debug("Set %s=%s", var, os.environ[var])


def tk_dialogs_available() -> bool:
    """Return True if a native dialog can actually be opened right now.

    Stronger than ``import tkinter`` — it constructs and tears down a real root
    window, which is where a broken Tcl installation actually shows up.
    """
    try:
        ensure_tcl_available()
        import tkinter as tk

        root = tk.Tk()
        root.destroy()
        return True
    except Exception as exc:  # noqa: BLE001 - any failure means "no dialogs"
        logger.info("Native dialogs unavailable: %s: %s", type(exc).__name__, exc)
        return False
