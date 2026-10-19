"""Tests for app.app_paths: where d-tach keeps files, from source and frozen (issue #79)."""

import shutil
import sys
from pathlib import Path

import pytest

from app import app_paths


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Pretend to be a PyInstaller onedir build whose bundle is a temp folder."""
    bundle = tmp_path / "d-tach" / "_internal"
    bundle.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(bundle), raising=False)
    return bundle


@pytest.fixture
def no_override(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the DTACH_DATA_DIR the root conftest sets, to test the platform defaults."""
    monkeypatch.delenv(app_paths.DATA_DIR_ENV, raising=False)


class TestFrozenOrNot:
    def test_not_frozen_from_source(self) -> None:
        assert app_paths.is_frozen() is False

    def test_frozen_when_pyinstaller_sets_the_flag(self, frozen: Path) -> None:
        assert app_paths.is_frozen() is True


class TestBundleDir:
    def test_source_bundle_is_the_project_root(self) -> None:
        root = app_paths.bundle_dir()
        assert (root / "tray.py").is_file()
        assert (root / "app" / "templates").is_dir()
        assert (root / "app" / "static").is_dir()
        assert (root / "app" / "data").is_dir()

    def test_frozen_bundle_is_meipass(self, frozen: Path) -> None:
        assert app_paths.bundle_dir() == frozen

    def test_legacy_settings_sit_in_the_bundle(self, frozen: Path) -> None:
        assert app_paths.legacy_settings_path() == frozen / "user_settings.json"


class TestUserDataDir:
    def test_override_wins(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setenv(app_paths.DATA_DIR_ENV, str(tmp_path / "custom"))
        assert app_paths.user_data_dir() == tmp_path / "custom"

    def test_windows_uses_local_appdata(self, no_override, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
        assert app_paths.user_data_dir() == tmp_path / "Local" / "d-tach"

    def test_macos_uses_application_support(self, no_override, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        assert app_paths.user_data_dir() == tmp_path / "Library" / "Application Support" / "d-tach"

    def test_linux_uses_xdg_data_home(self, no_override, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "share"))
        assert app_paths.user_data_dir() == tmp_path / "share" / "d-tach"

    def test_linux_falls_back_to_local_share(self, no_override, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        assert app_paths.user_data_dir() == tmp_path / ".local" / "share" / "d-tach"

    def test_same_folder_frozen_or_not(self, isolated_user_data_dir: Path, frozen: Path) -> None:
        assert app_paths.user_data_dir() == isolated_user_data_dir

    def test_settings_models_and_log_live_in_it(self, isolated_user_data_dir: Path) -> None:
        assert app_paths.settings_path() == isolated_user_data_dir / "user_settings.json"
        assert app_paths.models_dir() == isolated_user_data_dir / "models"
        assert app_paths.log_path() == isolated_user_data_dir / "logs" / "d-tach.log"

    def test_settings_never_resolve_into_the_bundle(self, frozen: Path) -> None:
        assert frozen not in app_paths.settings_path().parents


class TestResolveSettingsPath:
    @pytest.fixture
    def legacy(self, frozen: Path) -> Path:
        path = frozen / "user_settings.json"
        path.write_text('{"ai_api_token": "old-token"}', encoding="utf-8")
        return path

    def test_fresh_install_uses_the_per_user_file(self, frozen: Path) -> None:
        assert app_paths.resolve_settings_path() == app_paths.settings_path()
        assert not app_paths.settings_path().exists()

    def test_legacy_file_is_copied_once(self, legacy: Path) -> None:
        target = app_paths.resolve_settings_path()
        assert target == app_paths.settings_path()
        assert target.read_text(encoding="utf-8") == '{"ai_api_token": "old-token"}'
        assert legacy.exists(), "the legacy file is copied, not moved"

    def test_existing_per_user_file_is_not_overwritten(self, legacy: Path) -> None:
        target = app_paths.settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('{"ai_api_token": "new-token"}', encoding="utf-8")

        assert app_paths.resolve_settings_path() == target
        assert target.read_text(encoding="utf-8") == '{"ai_api_token": "new-token"}'

    def test_failed_copy_falls_back_to_the_legacy_file(self, legacy: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        def _boom(*args, **kwargs):
            raise PermissionError("read-only")

        monkeypatch.setattr(shutil, "copy2", _boom)
        assert app_paths.resolve_settings_path() == legacy

    def test_source_install_carries_its_file_over(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        project = tmp_path / "checkout"
        project.mkdir()
        (project / "user_settings.json").write_text('{"hashing_secret": "pepper"}', encoding="utf-8")
        monkeypatch.setattr(app_paths, "_PROJECT_ROOT", project)

        target = app_paths.resolve_settings_path()
        assert target == app_paths.settings_path()
        assert target.read_text(encoding="utf-8") == '{"hashing_secret": "pepper"}'

    def test_settings_survive_replacing_the_app_folder(self, legacy: Path, frozen: Path) -> None:
        from app.services.user_settings import UserSettings

        settings = UserSettings(settings_path=app_paths.resolve_settings_path())
        settings.hashing_secret = "pepper"
        settings.save()

        shutil.rmtree(frozen)  # an update replaces the whole app folder
        frozen.mkdir()

        reloaded = UserSettings(settings_path=app_paths.resolve_settings_path())
        assert reloaded.hashing_secret == "pepper"
        assert reloaded.ai_api_token == "old-token"
