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


class TestLanguageManagementDefaults:
    def test_fresh_install_has_setup_incomplete(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        assert settings.language_setup_complete is False

    def test_fresh_install_enables_only_english(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        assert settings.enabled_languages == ["en"]

    def test_fresh_install_defaults_to_eager_loading(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        assert settings.loading_strategy == "eager"


class TestLanguageManagementSetters:
    def test_enabled_languages_round_trip(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.enabled_languages = ["en", "nl"]
        settings.save()

        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.enabled_languages == ["en", "nl"]

    def test_loading_strategy_round_trip(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.loading_strategy = "lazy"
        settings.save()

        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.loading_strategy == "lazy"

    def test_invalid_loading_strategy_raises(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        with pytest.raises(ValueError):
            settings.loading_strategy = "sometimes"

    def test_language_setup_complete_round_trip(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.language_setup_complete = True
        settings.save()

        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.language_setup_complete is True


class TestLanguageManagementMigration:
    """A settings file written before issue #62 must be grandfathered in.

    Such a file already relied on both en+nl being loaded at startup, so it
    should not be surprised by the first-launch setup screen or lose Dutch.
    """

    def test_pre_existing_file_is_grandfathered_as_setup_complete(self, settings_path: Path) -> None:
        settings_path.write_text('{"port": 6000}', encoding="utf-8")
        settings = UserSettings(settings_path=settings_path)
        assert settings.language_setup_complete is True

    def test_pre_existing_file_is_grandfathered_with_both_languages(self, settings_path: Path) -> None:
        settings_path.write_text('{"port": 6000}', encoding="utf-8")
        settings = UserSettings(settings_path=settings_path)
        assert settings.enabled_languages == ["en", "nl"]

    def test_file_with_language_setup_complete_is_not_grandfathered(self, settings_path: Path) -> None:
        settings_path.write_text('{"language_setup_complete": false}', encoding="utf-8")
        settings = UserSettings(settings_path=settings_path)
        assert settings.language_setup_complete is False
        assert settings.enabled_languages == ["en"]


class TestKnownValuesDefaults:
    def test_fresh_install_has_no_known_values(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        assert settings.known_values == []


class TestKnownValuesSetter:
    def test_dict_entries_round_trip(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.known_values = [{"value": "Craig Bradley", "entity_type": "PERSON", "source": "manual"}]
        assert settings.known_values == [
            {"value": "Craig Bradley", "entity_type": "PERSON", "source": "manual", "rule": "any"}
        ]

    def test_missing_entity_type_defaults_to_person(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.known_values = [{"value": "12345"}]
        assert settings.known_values[0]["entity_type"] == "PERSON"

    def test_invalid_source_defaults_to_manual(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.known_values = [{"value": "x", "source": "bogus"}]
        assert settings.known_values[0]["source"] == "manual"

    def test_known_values_round_trip_through_save_and_reload(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.known_values = [{"value": "123456", "entity_type": "NUMERIC_ID", "source": "class_list"}]
        settings.save()

        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.known_values == [
            {"value": "123456", "entity_type": "NUMERIC_ID", "source": "class_list", "rule": "any"}
        ]


class TestKnownValuesMigration:
    """Pre-Step-4 known_values was a plain list[str]; must migrate without data loss."""

    def test_legacy_string_list_migrates_to_typed_dicts(self, settings_path: Path) -> None:
        settings_path.write_text('{"known_values": ["Craig Bradley", "Nick"]}', encoding="utf-8")
        settings = UserSettings(settings_path=settings_path)
        assert settings.known_values == [
            {"value": "Craig Bradley", "entity_type": "PERSON", "source": "manual", "rule": "any"},
            {"value": "Nick", "entity_type": "PERSON", "source": "manual", "rule": "any"},
        ]

    def test_blank_legacy_strings_are_dropped(self, settings_path: Path) -> None:
        settings_path.write_text('{"known_values": ["Craig", "  ", ""]}', encoding="utf-8")
        settings = UserSettings(settings_path=settings_path)
        assert [v["value"] for v in settings.known_values] == ["Craig"]

    def test_already_typed_entries_pass_through(self, settings_path: Path) -> None:
        settings_path.write_text(
            '{"known_values": [{"value": "123456", "entity_type": "NUMERIC_ID", "source": "class_list"}]}',
            encoding="utf-8",
        )
        settings = UserSettings(settings_path=settings_path)
        assert settings.known_values == [
            {"value": "123456", "entity_type": "NUMERIC_ID", "source": "class_list", "rule": "any"}
        ]

    def test_entry_saved_before_v140_loads_as_rule_any_with_no_name_part(
        self, settings_path: Path
    ) -> None:
        settings_path.write_text(
            '{"known_values": [{"value": "An Jansen", "entity_type": "PERSON", "source": "class_list"}]}',
            encoding="utf-8",
        )
        entry = UserSettings(settings_path=settings_path).known_values[0]
        assert entry["rule"] == "any"
        assert "name_part" not in entry

    def test_rule_and_name_part_survive_save_and_reload(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.known_values = [{
            "value": "Will", "entity_type": "PERSON", "source": "class_list",
            "rule": "capital", "name_part": "first",
        }]
        settings.save()
        entry = UserSettings(settings_path=settings_path).known_values[0]
        assert entry["rule"] == "capital"
        assert entry["name_part"] == "first"

    def test_unknown_rule_and_name_part_are_cleaned(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.known_values = [{"value": "x", "rule": "bogus", "name_part": "bogus"}]
        entry = settings.known_values[0]
        assert entry["rule"] == "any"
        assert "name_part" not in entry


class TestClassListFields:
    def test_defaults_are_empty(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        assert settings.class_list_path == ""
        assert settings.class_list_column_mapping == {}

    def test_round_trip_through_save_and_reload(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.class_list_path = "C:/roster.xlsx"
        settings.class_list_column_mapping = {"Name": "PERSON", "Student number": "NUMERIC_ID"}
        settings.save()

        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.class_list_path == "C:/roster.xlsx"
        assert reloaded.class_list_column_mapping == {"Name": "FULL_NAME", "Student number": "NUMERIC_ID"}

    def test_saved_person_mapping_is_read_as_full_name(self, settings_path: Path) -> None:
        settings_path.write_text(
            '{"class_list_column_mapping": {"Name": "PERSON"}}', encoding="utf-8"
        )
        settings = UserSettings(settings_path=settings_path)
        assert settings.class_list_column_mapping == {"Name": "FULL_NAME"}

    def test_new_column_types_round_trip(self, settings_path: Path) -> None:
        settings = UserSettings(settings_path=settings_path)
        settings.class_list_column_mapping = {"Voornaam": "FIRST_NAME", "Achternaam": "SURNAME"}
        settings.save()
        reloaded = UserSettings(settings_path=settings_path)
        assert reloaded.class_list_column_mapping == {"Voornaam": "FIRST_NAME", "Achternaam": "SURNAME"}

    def test_missing_fields_in_older_file_default_cleanly(self, settings_path: Path) -> None:
        settings_path.write_text('{"port": 6000}', encoding="utf-8")
        settings = UserSettings(settings_path=settings_path)
        assert settings.class_list_path == ""
        assert settings.class_list_column_mapping == {}
