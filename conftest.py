"""
Root conftest.py — adds the project root to sys.path so that pytest can
import the app package without needing to be invoked as 'python -m pytest'.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture(autouse=True)
def isolated_user_data_dir(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the per-user data folder at a temp folder for every test.

    Without this a test could read or delete the developer's real settings and
    downloaded models (see app/app_paths.py).
    """
    data_dir = tmp_path_factory.mktemp("user-data")
    monkeypatch.setenv("DTACH_DATA_DIR", str(data_dir))
    return data_dir
