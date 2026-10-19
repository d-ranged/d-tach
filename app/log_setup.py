"""Log file for d-tach, so a windowed build with no console still leaves a trace.

The tray entry point calls :func:`configure_logging` before anything else. Log
records go to a rotating file in the per-user folder, and to the console as
well when there is one (source runs and the console build).
"""
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final, Optional

LOG_FORMAT: Final[str] = "%(asctime)s %(levelname)s %(name)s: %(message)s"
LOG_MAX_BYTES: Final[int] = 1024 * 1024
LOG_BACKUP_COUNT: Final[int] = 3

_logger = logging.getLogger(__name__)


def configure_logging(log_file: Path, level: int = logging.INFO) -> Optional[Path]:
    """Send log records to ``log_file`` (rotating) and to stderr when it exists.

    Uncaught exceptions, on the main thread and on worker threads, are logged
    too. Returns the log file path, or None if the file could not be opened;
    d-tach still starts then, it just logs to the console only.
    """
    root = logging.getLogger()
    root.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT)

    # A windowed build has no stderr at all (sys.stderr is None).
    if sys.stderr is not None:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    opened: Optional[Path] = log_file
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)
    except OSError as exc:
        _logger.error("Could not open the log file %s: %s", log_file, exc)
        opened = None

    _install_exception_hooks()
    return opened


def _install_exception_hooks() -> None:
    """Log uncaught exceptions instead of losing them with the missing console."""

    def _log_uncaught(exc_type, exc_value, exc_traceback) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        _logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    def _log_uncaught_thread(args: threading.ExceptHookArgs) -> None:
        if args.exc_type is SystemExit:
            return
        thread_name = args.thread.name if args.thread is not None else "unknown"
        _logger.critical(
            "Uncaught exception in thread %s",
            thread_name,
            exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
        )

    sys.excepthook = _log_uncaught
    threading.excepthook = _log_uncaught_thread
