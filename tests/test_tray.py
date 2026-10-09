"""Tests for tray.py helpers that don't require an actual tray icon or GUI."""

import plistlib
import socket
import sys
from pathlib import Path

import pytest

import tray
from app import native_dialogs
from tray import _is_port_available, _offer_startup_registration, _prompt_startup_registration, _wait_for_server


class TestIsPortAvailable:
    def test_free_port_is_available(self) -> None:
        # Bind to port 0 to let the OS hand back a genuinely free port, then release it.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            free_port = probe.getsockname()[1]

        assert _is_port_available(free_port) is True

    def test_occupied_port_is_not_available(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
            holder.bind(("127.0.0.1", 0))
            holder.listen(1)
            occupied_port = holder.getsockname()[1]

            assert _is_port_available(occupied_port) is False


class TestWaitForServer:
    def test_returns_true_once_something_is_listening(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as holder:
            holder.bind(("127.0.0.1", 0))
            holder.listen(1)
            port = holder.getsockname()[1]

            assert _wait_for_server(port, timeout=5) is True

    def test_returns_false_when_nothing_binds(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]

        assert _wait_for_server(port, timeout=1) is False


class _FakeSettings:
    """Minimal stand-in for UserSettings covering the startup-prompt fields."""

    def __init__(self, shown: bool = False) -> None:
        self.tray_startup_prompt_shown = shown
        self.saved = False

    def save(self) -> None:
        self.saved = True


class TestStartupPromptIsNonFatal:
    """A Python install without usable Tcl/Tk must not stop d-tach from starting.

    Regression guard: tk.Tk() raises TclError (not ImportError) on installs that
    ship tkinter without its data files, which previously killed the tray process
    before the Flask server thread was ever started.
    """

    def test_prompt_returns_false_when_tk_is_broken(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom() -> None:
            raise RuntimeError("Can't find a usable init.tcl")

        monkeypatch.setattr(native_dialogs, "ensure_tcl_available", _boom)
        monkeypatch.setattr(native_dialogs, "needs_child_process", lambda platform=None: False)

        assert _prompt_startup_registration() is False

    def test_offer_still_records_the_prompt_when_it_cannot_be_shown(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(tray, "_prompt_startup_registration", lambda: False)
        settings = _FakeSettings(shown=False)

        _offer_startup_registration(settings)

        assert settings.tray_startup_prompt_shown is True
        assert settings.saved is True

    def test_offer_does_nothing_when_already_shown(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _should_not_run() -> bool:
            raise AssertionError("prompt must not be shown a second time")

        monkeypatch.setattr(tray, "_prompt_startup_registration", _should_not_run)
        settings = _FakeSettings(shown=True)

        _offer_startup_registration(settings)

        assert settings.saved is False

    def test_registration_failure_does_not_propagate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom() -> None:
            raise OSError("registry unavailable")

        monkeypatch.setattr(tray, "_prompt_startup_registration", lambda: True)
        monkeypatch.setattr(tray, "_register_startup_windows", _boom)
        monkeypatch.setattr(tray, "_register_startup_macos", _boom)
        monkeypatch.setattr(tray.sys, "platform", "win32")
        settings = _FakeSettings(shown=False)

        _offer_startup_registration(settings)

        assert settings.tray_startup_prompt_shown is True


# ---------------------------------------------------------------------------
# Frozen build: login entry, browser tab (issue #79)
# ---------------------------------------------------------------------------


@pytest.fixture
def frozen_windows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    exe = tmp_path / "d-tach" / "d-tach.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return exe


@pytest.fixture
def frozen_macos_app(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    bundle = tmp_path / "Applications" / "d-tach.app"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(bundle / "Contents" / "MacOS" / "d-tach"))
    return bundle


class TestStartupLaunchCommand:
    def test_frozen_registers_the_exe_alone(self, frozen_windows: Path) -> None:
        assert tray._startup_launch_command() == f'"{frozen_windows}" --at-login'

    def test_source_registers_interpreter_and_script(self) -> None:
        command = tray._startup_launch_command()
        assert command.endswith(f'"{Path(tray.__file__).resolve()}"')
        assert "--at-login" not in command


class TestLaunchAgent:
    def test_frozen_app_is_opened_through_launch_services(self, frozen_macos_app: Path) -> None:
        assert tray._launch_agent_arguments() == ["/usr/bin/open", "-a", str(frozen_macos_app), "--args", "--at-login"]

    def test_frozen_without_a_bundle_runs_the_executable(self, frozen_windows: Path) -> None:
        assert tray._launch_agent_arguments() == [str(frozen_windows), "--at-login"]

    def test_source_runs_interpreter_and_script(self) -> None:
        assert tray._launch_agent_arguments() == [sys.executable, str(Path(tray.__file__).resolve())]

    def test_plist_is_valid_and_escapes_paths(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        bundle = tmp_path / "Tools & Things" / "d-tach.app"
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        monkeypatch.setattr(sys, "executable", str(bundle / "Contents" / "MacOS" / "d-tach"))

        plist = plistlib.loads(tray._launch_agent_plist())

        assert plist["Label"] == tray.LAUNCH_AGENT_LABEL
        assert plist["RunAtLoad"] is True
        assert plist["ProgramArguments"][2] == str(bundle)


class TestShouldOpenBrowser:
    def test_launch_scripts_ask_for_it(self) -> None:
        assert tray._should_open_browser([], {"DTACH_OPEN_BROWSER": "1"}) is True

    def test_source_without_the_variable_does_not(self) -> None:
        assert tray._should_open_browser([], {}) is False

    def test_frozen_double_click_opens_a_tab(self, frozen_windows: Path) -> None:
        assert tray._should_open_browser([], {}) is True

    def test_frozen_at_login_does_not(self, frozen_windows: Path) -> None:
        assert tray._should_open_browser(["--at-login"], {}) is False
