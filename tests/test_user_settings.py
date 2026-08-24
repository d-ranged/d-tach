"""Tests for the UserSettings service class — port and startup-prompt fields."""

from pathlib import Path

import pytest

from app.services.user_settings import DEFAULT_PORT, MAX_PORT, MIN_PORT, UserSettings


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    """A user_settings.json path in a scratch directory, never the real one."""
    return tmp_path / "user_settings.json"


class TestPortDefaults:
    def test_default_port_is_5555(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        assert settings.port == DEFAULT_PORT == 5555

    def test_default_tray_startup_prompt_not_shown(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        assert settings.tray_startup_prompt_shown is False


class TestPortSetter:
    def test_valid_port_is_stored(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.port = 8080
        assert settings.port == 8080

    def test_port_below_minimum_raises(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        with pytest.raises(ValueError):
            settings.port = MIN_PORT - 1

    def test_port_above_maximum_raises(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        with pytest.raises(ValueError):
            settings.port = MAX_PORT + 1

    def test_non_numeric_port_raises(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        with pytest.raises(ValueError):
            settings.port = "not-a-port"


class TestPortPersistence:
    def test_port_round_trips_through_save_and_reload(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.port = 6000
        settings.save()

        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.port == 6000

    def test_out_of_range_value_in_file_falls_back_to_default(self, settings_path: Path) -> None:
        settings_path.write_text('{"port": 99}', encoding="utf-8")
        settings = UserSettings(settings_path=settings_path)
        assert settings.port == DEFAULT_PORT


class TestTrayStartupPromptPersistence:
    def test_flag_round_trips_through_save_and_reload(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.tray_startup_prompt_shown = True
        settings.save()

        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.tray_startup_prompt_shown is True
