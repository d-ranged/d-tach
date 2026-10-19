"""Tests for app.native_dialogs: Browse dialogs off Flask's thread on macOS (issue #79).

No real dialog opens here. The child process is simulated by running the
child-side entry point in-process with the Tk layer replaced.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

from app import app_paths, native_dialogs


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    exe = tmp_path / "d-tach" / "d-tach.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path / "d-tach" / "_internal"), raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    return exe


@pytest.fixture
def fake_tk(monkeypatch: pytest.MonkeyPatch) -> list:
    """Replace every Tk dialog with a canned answer, recording which ran."""
    calls: list = []

    def _make(kind, answer):
        def _handler(*args):
            calls.append((kind, args))
            return answer
        return _handler

    monkeypatch.setattr(native_dialogs, "_tk_pick_file", _make("file", "C:/docs/report.docx"))
    monkeypatch.setattr(native_dialogs, "_tk_pick_csv", _make("csv", "C:/docs/KEYREF_x.csv"))
    monkeypatch.setattr(native_dialogs, "_tk_pick_folder", _make("folder", ""))
    monkeypatch.setattr(native_dialogs, "_tk_ask_yes_no", _make("yes_no", True))
    monkeypatch.setattr(native_dialogs, "_tk_probe", _make("probe", True))
    return calls


@pytest.fixture
def simulated_child(monkeypatch: pytest.MonkeyPatch) -> list:
    """Make subprocess.run behave like the d-tach child: run run_dialog_child in-process."""
    commands: list = []

    def _run(command, **kwargs):
        commands.append(command)
        flag_at = command.index(native_dialogs.DIALOG_FLAG)
        code = native_dialogs.run_dialog_child(command[flag_at + 1:])
        return subprocess.CompletedProcess(command, code, "", "")

    monkeypatch.setattr(native_dialogs.subprocess, "run", _run)
    return commands


class TestWhereDialogsRun:
    def test_macos_needs_a_child_process(self) -> None:
        assert native_dialogs.needs_child_process("darwin") is True

    @pytest.mark.parametrize("platform", ["win32", "linux"])
    def test_windows_and_linux_run_in_process(self, platform: str) -> None:
        assert native_dialogs.needs_child_process(platform) is False

    def test_in_process_on_windows(self, monkeypatch: pytest.MonkeyPatch, fake_tk: list) -> None:
        monkeypatch.setattr(sys, "platform", "win32")

        def _no_subprocess(*args, **kwargs):
            raise AssertionError("Windows must not start a child process")

        monkeypatch.setattr(native_dialogs.subprocess, "run", _no_subprocess)
        assert native_dialogs.pick_file() == "C:/docs/report.docx"
        assert fake_tk == [("file", ())]


class TestChildCommand:
    def test_source_runs_tray_py_with_this_interpreter(self, tmp_path: Path) -> None:
        command = native_dialogs.child_command("file", tmp_path / "r.json")
        assert command[0] == sys.executable
        assert Path(command[1]) == app_paths.bundle_dir() / "tray.py"
        assert command[2:] == ["--dialog", "file", str(tmp_path / "r.json")]

    def test_frozen_runs_the_executable_itself(self, frozen: Path, tmp_path: Path) -> None:
        command = native_dialogs.child_command("yes_no", tmp_path / "r.json", "d-tach", "Run at login?")
        assert command == [str(frozen), "--dialog", "yes_no", str(tmp_path / "r.json"), "d-tach", "Run at login?"]


class TestMacOSChildProcess:
    @pytest.fixture(autouse=True)
    def macos(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")

    def test_pick_file_comes_back_from_the_child(self, fake_tk: list, simulated_child: list) -> None:
        assert native_dialogs.pick_file() == "C:/docs/report.docx"
        assert len(simulated_child) == 1

    def test_cancel_comes_back_as_empty_string(self, fake_tk: list, simulated_child: list) -> None:
        assert native_dialogs.pick_folder() == ""

    def test_yes_no_passes_title_and_message(self, fake_tk: list, simulated_child: list) -> None:
        assert native_dialogs.ask_yes_no("d-tach", "Run at login?") is True
        assert fake_tk == [("yes_no", ("d-tach", "Run at login?"))]

    def test_probe_runs_in_the_child(self, fake_tk: list, simulated_child: list) -> None:
        assert native_dialogs.dialogs_available() is True
        assert len(simulated_child) == 1

    def test_child_error_is_raised_in_the_parent(
        self, monkeypatch: pytest.MonkeyPatch, simulated_child: list
    ) -> None:
        def _broken():
            raise RuntimeError("Can't find a usable init.tcl")

        monkeypatch.setattr(native_dialogs, "_tk_pick_csv", _broken)
        with pytest.raises(native_dialogs.DialogError, match="init.tcl"):
            native_dialogs.pick_csv()

    def test_child_that_dies_without_an_answer(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            native_dialogs.subprocess,
            "run",
            lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", "Segmentation fault"),
        )
        with pytest.raises(native_dialogs.DialogError, match="Segmentation fault"):
            native_dialogs.pick_file()

    def test_probe_failure_means_unavailable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            native_dialogs.subprocess,
            "run",
            lambda command, **kwargs: subprocess.CompletedProcess(command, 1, "", ""),
        )
        assert native_dialogs.dialogs_available() is False


class TestRunDialogChild:
    def test_writes_the_answer(self, tmp_path: Path, fake_tk: list) -> None:
        result = tmp_path / "r.json"
        assert native_dialogs.run_dialog_child(["csv", str(result)]) == 0
        assert json.loads(result.read_text(encoding="utf-8")) == {"result": "C:/docs/KEYREF_x.csv"}

    def test_writes_an_error_for_an_unknown_kind(self, tmp_path: Path) -> None:
        result = tmp_path / "r.json"
        assert native_dialogs.run_dialog_child(["nonsense", str(result)]) == 0
        assert "Unknown dialog kind" in json.loads(result.read_text(encoding="utf-8"))["error"]

    def test_missing_arguments(self) -> None:
        assert native_dialogs.run_dialog_child(["file"]) == 2


class TestBrowseRoutes:
    @pytest.fixture
    def client(self, monkeypatch: pytest.MonkeyPatch):
        from flask import Flask

        from app.routes import browse_routes

        browse_routes._dialogs_available.cache_clear()
        app = Flask(__name__)
        app.register_blueprint(browse_routes.bp)
        yield app.test_client()
        browse_routes._dialogs_available.cache_clear()

    def test_file_route_returns_the_dialog_answer(self, client, fake_tk: list) -> None:
        assert client.get("/browse/file").get_json() == {"path": "C:/docs/report.docx"}

    def test_status_reports_unavailable(self, client, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(native_dialogs, "dialogs_available", lambda: False)
        assert client.get("/browse/status").get_json() == {"available": False}
        assert client.get("/browse/folder").get_json()["tkinter_unavailable"] is True

    def test_dialog_failure_is_a_500_without_a_traceback(self, client, fake_tk: list, monkeypatch) -> None:
        def _broken():
            raise native_dialogs.DialogError("child crashed")

        monkeypatch.setattr(native_dialogs, "pick_csv", _broken)
        response = client.get("/browse/csv")
        assert response.status_code == 500
        assert response.get_json() == {"error": "child crashed"}
