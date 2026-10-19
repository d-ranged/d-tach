"""Smoke test for a packaged d-tach: start it, download English, anonymize a line.

Runs the built app with its own data folder and port, so a d-tach already
running on the machine and its settings are left alone. The first-run
"start at login" prompt is marked as shown, so no dialog waits for a click.

Command, from the repo root, after a build:

  python packaging/smoke_test.py dist/d-tach/d-tach.exe                   (Windows)
  python packaging/smoke_test.py dist/d-tach.app/Contents/MacOS/d-tach    (macOS)

Exits 0 when every check passes. Standard library only.
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Final, Optional

PORT: Final[int] = 5598
BASE_URL: Final[str] = f"http://127.0.0.1:{PORT}"
LANGUAGE: Final[str] = "en"
START_TIMEOUT_SECONDS: Final[int] = 60
DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 300
REQUEST_TIMEOUT_SECONDS: Final[int] = 60
POLL_SECONDS: Final[float] = 1.0
SAMPLE_TEXT: Final[str] = "Please send the report to Lotte Vermeulen at lotte.vermeulen@example.com."
MUST_DISAPPEAR: Final[tuple[str, ...]] = ("Lotte", "Vermeulen", "lotte.vermeulen@example.com")


def request_json(path: str, body: Optional[dict] = None) -> Any:
    """Send a GET, or a POST when body is given, and return the decoded JSON reply."""
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(BASE_URL + path, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return json.load(response)


def wait_for_ping(process: subprocess.Popen) -> None:
    """Wait until the app answers /ping as d-tach."""
    deadline = time.monotonic() + START_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"d-tach exited with code {process.returncode} before it answered")
        try:
            reply = request_json("/ping")
        except OSError:
            time.sleep(POLL_SECONDS)
            continue
        if reply.get("app") != "d-tach":
            raise RuntimeError(f"Something else answered on port {PORT}: {reply}")
        print(f"Started: d-tach {reply.get('version')}")
        return
    raise RuntimeError(f"d-tach did not answer within {START_TIMEOUT_SECONDS} s")


def install_language() -> None:
    """Download the English model through the app and wait until it is installed."""
    status = request_json("/settings/languages/install", {"code": LANGUAGE})
    deadline = time.monotonic() + DOWNLOAD_TIMEOUT_SECONDS
    while status.get("state") == "downloading" and time.monotonic() < deadline:
        time.sleep(POLL_SECONDS)
        status = request_json(f"/settings/languages/install-status?code={LANGUAGE}")
    if status.get("state") != "done":
        raise RuntimeError(f"Language download did not finish: {status}")
    print(f"Downloaded language: {LANGUAGE}")


def anonymize_sample() -> None:
    """Anonymize the sample line and check the name and email are gone."""
    reply = request_json("/text/anonymize", {"text": SAMPLE_TEXT, "language": LANGUAGE})
    result = reply.get("anonymized_text", "")
    left = [value for value in MUST_DISAPPEAR if value in result]
    if reply.get("error") or left:
        raise RuntimeError(f"Anonymize failed, still in the clear: {left}, reply: {reply}")
    print(f"Anonymized: {result}")


def run(executable: Path) -> None:
    """Start the app in a scratch data folder, run the checks, then stop it."""
    with tempfile.TemporaryDirectory(prefix="d-tach-smoke-") as data_dir:
        (Path(data_dir) / "user_settings.json").write_text(
            json.dumps({"tray_startup_prompt_shown": True}), encoding="utf-8"
        )
        env = {**os.environ, "DTACH_DATA_DIR": data_dir, "DTACH_PORT": str(PORT)}
        process = subprocess.Popen([str(executable), "--at-login"], env=env)
        try:
            wait_for_ping(process)
            install_language()
            anonymize_sample()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
            log_file = Path(data_dir) / "logs" / "d-tach.log"
            if log_file.exists():
                print("--- d-tach log ---")
                print(log_file.read_text(encoding="utf-8", errors="replace"))


def main() -> None:
    """Parse the executable path and run the smoke test."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("executable", type=Path, help="the built d-tach executable")
    args = parser.parse_args()
    try:
        run(args.executable)
    except (RuntimeError, OSError) as exc:
        print(f"Smoke test failed: {exc}", file=sys.stderr)
        sys.exit(1)
    print("Smoke test passed")


if __name__ == "__main__":
    main()
