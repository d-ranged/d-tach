"""d-tach system tray entry point.

Starts the Flask server in a background thread and gives the user a
persistent tray icon to open or quit the application. This is the normal
launch path — run.py and serve.py remain available for development use.
"""
import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

import pystray
from PIL import Image

from app import create_app

logger = logging.getLogger(__name__)

TRAY_APP_NAME = "d-tach"
ICON_PATH = Path(__file__).resolve().parent / "app" / "static" / "favicon.png"
PORT_IN_USE_NOTIFICATION_SECONDS = 5
STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
LAUNCH_AGENT_LABEL = "org.d-ranged.d-tach"


def _is_port_available(port: int) -> bool:
    """Return True if a socket can bind to 127.0.0.1:port right now."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _notify_port_in_use(port: int) -> None:
    """Show a transient system notification that the port is already in use."""
    image = Image.open(ICON_PATH)
    icon = pystray.Icon(TRAY_APP_NAME, image, TRAY_APP_NAME)

    def _show(icon: pystray.Icon) -> None:
        icon.visible = True
        icon.notify(f"d-tach could not start — port {port} is in use", TRAY_APP_NAME)
        time.sleep(PORT_IN_USE_NOTIFICATION_SECONDS)
        icon.stop()

    icon.run(setup=_show)


def _startup_launch_command() -> str:
    """Return the command line used to relaunch this tray app at login.

    Prefers pythonw.exe when available so no console window flashes on login.
    """
    executable = Path(sys.executable)
    pythonw = executable.parent / "pythonw.exe"
    interpreter = pythonw if pythonw.exists() else executable
    script = Path(__file__).resolve()
    return f'"{interpreter}" "{script}"'


def _register_startup_windows() -> None:
    """Register this script to run on login via the current user's Run key."""
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, TRAY_APP_NAME, 0, winreg.REG_SZ, _startup_launch_command())


def _register_startup_macos() -> None:
    """Write a LaunchAgent plist so this script runs on login."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    script = Path(__file__).resolve()
    plist_path.write_text(
        f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{LAUNCH_AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{sys.executable}</string>
        <string>{script}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
""",
        encoding="utf-8",
    )


def _prompt_startup_registration() -> bool:
    """Ask the user (via a native dialog) whether to run d-tach at login."""
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        return False

    root = tk.Tk()
    root.withdraw()
    root.wm_attributes("-topmost", True)
    answer = messagebox.askyesno(
        "d-tach",
        "Run d-tach automatically when you log in?\n\n"
        "This adds a startup entry so d-tach is always available in your system tray.",
    )
    root.destroy()
    return answer


def _offer_startup_registration(settings) -> None:
    """Show the one-time startup-registration prompt on first launch only."""
    if settings.tray_startup_prompt_shown:
        return

    if sys.platform in ("win32", "darwin") and _prompt_startup_registration():
        try:
            if sys.platform == "win32":
                _register_startup_windows()
            else:
                _register_startup_macos()
        except OSError as exc:
            logger.error("Failed to register startup entry: %s", exc)

    settings.tray_startup_prompt_shown = True
    settings.save()


def main() -> None:
    """Start the Flask server in a background thread and run the tray icon."""
    app = create_app()
    settings = app.user_settings
    port = int(os.environ.get("DTACH_PORT", settings.port))

    if not _is_port_available(port):
        logger.error("Port %d is already in use.", port)
        _notify_port_in_use(port)
        sys.exit(1)

    _offer_startup_registration(settings)

    server_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "127.0.0.1", "port": port, "debug": False, "use_reloader": False},
        daemon=True,
    )
    server_thread.start()

    def open_dtach(icon: pystray.Icon = None, item: pystray.MenuItem = None) -> None:
        webbrowser.open(f"http://localhost:{app.user_settings.port}")

    def quit_dtach(icon: pystray.Icon, item: pystray.MenuItem) -> None:
        icon.stop()

    menu = pystray.Menu(
        pystray.MenuItem("Open d-tach", open_dtach, default=True),
        pystray.MenuItem("Quit", quit_dtach),
    )
    icon = pystray.Icon(TRAY_APP_NAME, Image.open(ICON_PATH), TRAY_APP_NAME, menu)
    icon.run()


if __name__ == "__main__":
    main()
