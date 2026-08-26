"""Tests for tray.py helpers that don't require an actual tray icon or GUI."""

import socket

import pytest

import tray
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

        monkeypatch.setattr(tray, "ensure_tcl_available", _boom)

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
