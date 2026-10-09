"""d-tach system tray entry point.

Starts the Flask server in a background thread and gives the user a
persistent tray icon to open or quit the application. This is the normal
launch path — run.py and serve.py remain available for development use.

It is also the entry point of the frozen (PyInstaller) build, so it handles
two command-line flags: ``--at-login`` (started by the login entry, so no
browser tab opens) and ``--dialog`` (a child process that shows one native
dialog for the macOS Browse buttons, see app/native_dialogs.py).
"""
import json
import logging
import os
import plistlib
import socket
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path
from typing import Mapping, Optional, Sequence

import pystray
from PIL import Image

from app import APP_ID, __version__, create_app, native_dialogs
from app.app_paths import bundle_dir, is_frozen, log_path, resolve_settings_path, user_data_dir
from app.log_setup import configure_logging
from app.services.user_settings import UserSettings

logger = logging.getLogger(__name__)

TRAY_APP_NAME = "d-tach"
ICON_PATH = bundle_dir() / "app" / "static" / "favicon.png"
PORT_IN_USE_NOTIFICATION_SECONDS = 5
SERVER_READY_TIMEOUT_SECONDS = 30
PING_TIMEOUT_SECONDS = 2
STARTUP_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
LAUNCH_AGENT_LABEL = "org.d-ranged.d-tach"
AT_LOGIN_FLAG = "--at-login"
OPEN_BROWSER_ENV = "DTACH_OPEN_BROWSER"
MACOS_OPEN_COMMAND = "/usr/bin/open"
APP_BUNDLE_SUFFIX = ".app"


def _is_port_available(port: int) -> bool:
    """Return True if a socket can bind to 127.0.0.1:port right now.

    On Windows SO_REUSEADDR lets a second socket bind a port that is already
    listening, so a running d-tach went unnoticed and two ran at once.
    SO_EXCLUSIVEADDRUSE asks for the port alone. Elsewhere SO_REUSEADDR only
    skips TIME_WAIT leftovers from the last run.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sys.platform == "win32":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def _is_dtach_running(port: int) -> bool:
    """Return True if the program listening on 127.0.0.1:port is d-tach."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=PING_TIMEOUT_SECONDS) as response:
            return json.load(response).get("app") == APP_ID
    except (OSError, ValueError, AttributeError):
        return False


def _handle_port_in_use(port: int, argv: Sequence[str], environ: Mapping[str, str]) -> int:
    """Deal with a start whose port is taken and return the exit code.

    If d-tach already has the port, this start hands over to it: it opens the
    running one in the browser (not when started at login) and exits. Anything
    else on the port gets the "port in use" notification.
    """
    if _is_dtach_running(port):
        logger.info("d-tach is already running on port %d.", port)
        if _should_open_browser(argv, environ):
            webbrowser.open(f"http://localhost:{port}")
        return 0
    logger.error("Port %d is already in use.", port)
    _notify_port_in_use(port)
    return 1


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

    Frozen, that is the d-tach executable alone. From source it prefers
    pythonw.exe when available so no console window flashes on login.
    """
    executable = Path(sys.executable)
    if is_frozen():
        return f'"{executable}" {AT_LOGIN_FLAG}'
    pythonw = executable.parent / "pythonw.exe"
    interpreter = pythonw if pythonw.exists() else executable
    script = Path(__file__).resolve()
    return f'"{interpreter}" "{script}"'


def _register_startup_windows() -> None:
    """Register d-tach to run on login via the current user's Run key."""
    import winreg

    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, STARTUP_REGISTRY_KEY, 0, winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, TRAY_APP_NAME, 0, winreg.REG_SZ, _startup_launch_command())


def _app_bundle(executable: Path) -> Optional[Path]:
    """Return the enclosing macOS .app bundle of an executable, if there is one."""
    for parent in executable.parents:
        if parent.suffix == APP_BUNDLE_SUFFIX:
            return parent
    return None


def _launch_agent_arguments() -> list[str]:
    """Return the ProgramArguments the macOS LaunchAgent runs at login.

    Frozen inside a .app, the app is opened through LaunchServices like a
    double click. From source it is the interpreter and this script, as before.
    """
    executable = Path(sys.executable)
    if not is_frozen():
        return [str(executable), str(Path(__file__).resolve())]
    bundle = _app_bundle(executable)
    if bundle is None:
        return [str(executable), AT_LOGIN_FLAG]
    return [MACOS_OPEN_COMMAND, "-a", str(bundle), "--args", AT_LOGIN_FLAG]


def _launch_agent_plist() -> bytes:
    """Return the LaunchAgent plist that starts d-tach at login."""
    return plistlib.dumps(
        {
            "Label": LAUNCH_AGENT_LABEL,
            "ProgramArguments": _launch_agent_arguments(),
            "RunAtLoad": True,
        }
    )


def _register_startup_macos() -> None:
    """Write a LaunchAgent plist so d-tach runs on login."""
    plist_path = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    plist_path.write_bytes(_launch_agent_plist())


def _prompt_startup_registration() -> bool:
    """Ask the user (via a native dialog) whether to run d-tach at login.

    Returns False when no dialog can be shown. This is a convenience prompt, so
    every failure here is non-fatal — a Python install that ships tkinter without
    usable Tcl data files must not stop d-tach from starting.
    """
    try:
        return native_dialogs.ask_yes_no(
            "d-tach",
            "Run d-tach automatically when you log in?\n\n"
            "This adds a startup entry so d-tach is always available in your system tray.",
        )
    except Exception as exc:  # noqa: BLE001 - never let the prompt block startup
        logger.warning(
            "Could not show the startup-registration prompt (%s: %s). "
            "Skipping it; d-tach will start normally.",
            type(exc).__name__,
            exc,
        )
        return False


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
        except Exception as exc:  # noqa: BLE001 - registration is optional
            logger.error("Failed to register startup entry: %s", exc)

    # Recorded even when the prompt could not be shown, so a machine that can
    # never display it doesn't retry the prompt on every launch.
    try:
        settings.tray_startup_prompt_shown = True
        settings.save()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to save startup-prompt state: %s", exc)


def _wait_for_server(port: int, timeout: float = SERVER_READY_TIMEOUT_SECONDS) -> bool:
    """Block until the local server accepts a connection on port, or timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.25)
    return False


def _should_open_browser(argv: Sequence[str], environ: Mapping[str, str]) -> bool:
    """Return True if this start should open a browser tab.

    The launch scripts ask for it. A frozen build opens one on a double click,
    but not when the login entry starts it. The same rule applies when a start
    finds d-tach already running and hands over to it.
    """
    if environ.get(OPEN_BROWSER_ENV) == "1":
        return True
    return is_frozen() and AT_LOGIN_FLAG not in argv


def main() -> None:
    """Start the Flask server in a background thread and run the tray icon."""
    log_file = configure_logging(log_path())
    logger.info(
        "Starting d-tach %s (%s). Data folder: %s. Log file: %s.",
        __version__,
        "frozen" if is_frozen() else "from source",
        user_data_dir(),
        log_file,
    )
    # Checked before create_app loads the language models, so a second start
    # hands over to the running d-tach without a wait.
    port = int(os.environ.get("DTACH_PORT", UserSettings(settings_path=resolve_settings_path()).port))
    if not _is_port_available(port):
        sys.exit(_handle_port_in_use(port, sys.argv[1:], os.environ))

    app = create_app()
    settings = app.user_settings

    # The server comes up before anything optional runs, so a failure in the
    # first-launch prompt below can never leave the user with a dead port.
    server_thread = threading.Thread(
        target=app.run,
        kwargs={"host": "127.0.0.1", "port": port, "debug": False, "use_reloader": False},
        daemon=True,
    )
    server_thread.start()

    if not _wait_for_server(port):
        logger.error("Server did not start listening on port %d within the timeout.", port)
        sys.exit(1)

    print(f"d-tach is running on http://localhost:{port}", flush=True)

    # Logging in shouldn't pop a browser open.
    if _should_open_browser(sys.argv[1:], os.environ):
        webbrowser.open(f"http://localhost:{port}")

    _offer_startup_registration(settings)

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
    if len(sys.argv) > 1 and sys.argv[1] == native_dialogs.DIALOG_FLAG:
        sys.exit(native_dialogs.run_dialog_child(sys.argv[2:]))
    main()
