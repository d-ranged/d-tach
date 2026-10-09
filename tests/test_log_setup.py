"""Tests for app.log_setup: a log file in the per-user folder (issue #79)."""

import logging
import sys
import threading
from pathlib import Path

import pytest

from app.log_setup import configure_logging


@pytest.fixture(autouse=True)
def restore_logging():
    """Put the root logger and exception hooks back after each test."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    excepthook, thread_hook = sys.excepthook, threading.excepthook
    yield
    for handler in root.handlers:
        if handler not in handlers:
            handler.close()
    root.handlers = handlers
    root.setLevel(level)
    sys.excepthook, threading.excepthook = excepthook, thread_hook


def _flush() -> None:
    for handler in logging.getLogger().handlers:
        handler.flush()


def test_records_reach_the_log_file(tmp_path: Path) -> None:
    log_file = tmp_path / "logs" / "d-tach.log"
    assert configure_logging(log_file) == log_file

    logging.getLogger("app.test").warning("could not read report.pdf")
    _flush()

    assert "could not read report.pdf" in log_file.read_text(encoding="utf-8")


def test_uncaught_thread_exceptions_are_logged(tmp_path: Path) -> None:
    log_file = tmp_path / "d-tach.log"
    configure_logging(log_file)

    def _crash() -> None:
        raise ValueError("worker blew up")

    worker = threading.Thread(target=_crash, name="download-nl")
    worker.start()
    worker.join()
    _flush()

    text = log_file.read_text(encoding="utf-8")
    assert "Uncaught exception in thread download-nl" in text
    assert "worker blew up" in text


def test_windowed_build_without_stderr(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stderr", None)
    log_file = tmp_path / "d-tach.log"

    configure_logging(log_file)
    logging.getLogger("app.test").info("started")
    _flush()

    assert "started" in log_file.read_text(encoding="utf-8")


def test_unwritable_log_folder_does_not_stop_startup(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("", encoding="utf-8")

    assert configure_logging(blocker / "d-tach.log") is None
