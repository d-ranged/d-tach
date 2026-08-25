"""Tests for the /settings/* routes and the read-only rule they impose on runs.

Settings is the only writer. Every value a run depends on — detection, hashing,
Excel handling, folder output, default language — is stored once here and read by
Text, Document and AI mode alike. That has two testable halves, and both are
covered below: the endpoints that write, and the run endpoints that must not.

The second half matters more than it looks. Before this split, a Document Mode
run persisted whatever flags its request happened to carry, so a caller that
simply omitted "anonymize_dates" turned date detection off globally — including
for the next AI Mode run, which never asked for that and had no way to notice.
"""

import json
from pathlib import Path

import pytest
from flask import Flask

from app.routes.document_routes import bp as document_bp
from app.routes.settings_routes import bp as settings_bp
from app.routes.text_routes import bp as text_bp
from app.services.anonymizer import Anonymizer
from app.services.file_processor import FileProcessor
from app.services.language_detector import LanguageDetector
from app.services.user_settings import UserSettings


@pytest.fixture
def settings_path(tmp_path: Path) -> Path:
    return tmp_path / "user_settings.json"


@pytest.fixture
def user_settings(settings_path: Path) -> UserSettings:
    return UserSettings(settings_path=settings_path)


@pytest.fixture
def app(user_settings: UserSettings) -> Flask:
    """Flask app with only the settings blueprint — no language registry needed."""
    flask_app = Flask(__name__)
    flask_app.register_blueprint(settings_bp)
    flask_app.user_settings = user_settings  # type: ignore[attr-defined]
    return flask_app


@pytest.fixture
def client(app: Flask):
    return app.test_client()


def saved_json(settings_path: Path) -> dict:
    """Read the settings file straight from disk, bypassing the in-memory object."""
    return json.loads(settings_path.read_text(encoding="utf-8"))


class TestDetection:
    def test_partial_update_leaves_other_fields_alone(self, client, settings_path: Path) -> None:
        client.post("/settings/detection", json={"anonymize_locations": True})
        resp = client.post("/settings/detection", json={"anonymize_dates": True})

        body = resp.get_json()
        assert resp.status_code == 200
        assert body["anonymize_dates"] is True
        assert body["anonymize_locations"] is True
        assert saved_json(settings_path)["anonymize_locations"] is True

    def test_omitted_field_is_not_reset_to_false(self, client, user_settings) -> None:
        """The bug this whole split exists to prevent: absent must mean "leave it"."""
        client.post("/settings/detection", json={"anonymize_urls": True})
        client.post("/settings/detection", json={"anonymize_dates": True})

        assert user_settings.anonymize_urls is True

    def test_numeric_id_and_digit_count_persist(self, client, settings_path: Path) -> None:
        resp = client.post(
            "/settings/detection",
            json={"numeric_id_enabled": True, "digit_count": 6},
        )

        assert resp.get_json()["digit_count"] == 6
        written = saved_json(settings_path)["pattern_config"]
        assert written["numeric_id_enabled"] is True
        assert written["digit_count"] == 6

    def test_check_file_names_persists(self, client, user_settings) -> None:
        client.post("/settings/detection", json={"check_file_names": True})

        assert user_settings.pattern_config.check_file_names is True

    def test_non_numeric_digit_count_returns_400(self, client) -> None:
        resp = client.post("/settings/detection", json={"digit_count": "seven"})

        assert resp.status_code == 400
        assert "error" in resp.get_json()


class TestHashing:
    def test_enable_with_secret(self, client, settings_path: Path) -> None:
        resp = client.post("/settings/hashing", json={"enabled": True, "secret": "pepper"})

        assert resp.get_json()["enabled"] is True
        assert saved_json(settings_path)["hashing_secret"] == "pepper"

    def test_enable_without_secret_returns_400(self, client, user_settings) -> None:
        resp = client.post("/settings/hashing", json={"enabled": True, "secret": "  "})

        assert resp.status_code == 400
        assert user_settings.hashing_enabled is False

    def test_secret_survives_disabling(self, client, user_settings) -> None:
        """Turning hashing off then on again must reproduce the same placeholders."""
        client.post("/settings/hashing", json={"enabled": True, "secret": "pepper"})
        client.post("/settings/hashing", json={"enabled": False, "secret": ""})

        assert user_settings.hashing_enabled is False
        assert user_settings.hashing_secret == "pepper"


class TestExcel:
    def test_column_names_round_trip_as_a_list(self, client, user_settings) -> None:
        resp = client.post(
            "/settings/excel",
            json={"excel_column_names": " stnum , email ,, phone "},
        )

        assert resp.get_json()["excel_column_names"] == "stnum, email, phone"
        assert user_settings.excel_column_names == ["stnum", "email", "phone"]

    def test_generic_toggle_persists(self, client, settings_path: Path) -> None:
        client.post("/settings/excel", json={"excel_generic_enabled": True})

        assert saved_json(settings_path)["excel_generic_enabled"] is True


class TestFolderOutput:
    def test_output_mode_persists(self, client, user_settings) -> None:
        resp = client.post("/settings/folder-output", json={"output_mode": "subfolder"})

        assert resp.get_json()["output_mode"] == "subfolder"
        assert user_settings.output_mode == "subfolder"

    def test_invalid_output_mode_returns_400(self, client, user_settings) -> None:
        resp = client.post("/settings/folder-output", json={"output_mode": "sideways"})

        assert resp.status_code == 400
        assert user_settings.output_mode == "prefix"

    def test_pass_through_extensions_are_normalized(self, client, user_settings) -> None:
        client.post(
            "/settings/folder-output",
            json={"pass_through_extensions": "sql, .MP4 , yml"},
        )

        assert user_settings.pass_through_extensions == [".sql", ".mp4", ".yml"]


class TestDefaultLanguage:
    def test_sets_language(self, client, settings_path: Path) -> None:
        resp = client.post("/settings/default-language", json={"language": "nl"})

        assert resp.get_json()["language"] == "nl"
        assert saved_json(settings_path)["language"] == "nl"

    def test_unsupported_language_returns_400(self, client, user_settings) -> None:
        resp = client.post("/settings/default-language", json={"language": "de"})

        assert resp.status_code == 400
        assert user_settings.language == "en"


@pytest.fixture(scope="session")
def services() -> tuple[Anonymizer, LanguageDetector, FileProcessor]:
    """Shared service instances so spaCy models load once for the whole module."""
    anonymizer = Anonymizer()
    language_detector = LanguageDetector()
    return anonymizer, language_detector, FileProcessor(
        anonymizer=anonymizer, language_detector=language_detector
    )


@pytest.fixture
def run_app(user_settings: UserSettings, services) -> Flask:
    """App with the two run blueprints wired up, for the no-write-back tests."""
    anonymizer, language_detector, file_processor = services
    flask_app = Flask(__name__)
    flask_app.register_blueprint(text_bp)
    flask_app.register_blueprint(document_bp)
    flask_app.user_settings = user_settings  # type: ignore[attr-defined]
    flask_app.file_processor = file_processor  # type: ignore[attr-defined]
    flask_app.anonymizer = anonymizer  # type: ignore[attr-defined]
    flask_app.language_detector = language_detector  # type: ignore[attr-defined]
    return flask_app


@pytest.fixture
def run_client(run_app: Flask):
    return run_app.test_client()


class TestRunsDoNotWriteSettings:
    """A run reads the saved configuration and leaves it exactly as it found it."""

    def test_text_run_uses_saved_settings_as_defaults(
        self, client, run_client, user_settings
    ) -> None:
        client.post("/settings/detection", json={"numeric_id_enabled": True, "digit_count": 6})

        resp = run_client.post("/text/anonymize", json={"text": "Ref 123456 applies."})

        types = {e["type"] for e in resp.get_json()["entities"]}
        assert "NUMERIC_ID" in types

    def test_text_run_does_not_persist_its_overrides(
        self, client, run_client, settings_path: Path
    ) -> None:
        client.post("/settings/detection", json={"anonymize_dates": False})
        before = saved_json(settings_path)

        run_client.post(
            "/text/anonymize",
            json={"text": "Ali met Sam on 3 March.", "anonymize_dates": True},
        )

        assert saved_json(settings_path) == before

    def test_document_run_does_not_persist_its_overrides(
        self, client, run_client, settings_path: Path, tmp_path: Path
    ) -> None:
        client.post("/settings/detection", json={"anonymize_locations": False})
        before = saved_json(settings_path)

        source = tmp_path / "note.md"
        source.write_text("Ali lives in Deventer.", encoding="utf-8")
        resp = run_client.post(
            "/document/process-file",
            json={"file_path": str(source), "anonymize_locations": True},
        )

        assert resp.status_code == 200
        assert saved_json(settings_path) == before

    def test_document_run_omitting_a_flag_does_not_disable_it(
        self, client, run_client, user_settings, tmp_path: Path
    ) -> None:
        """The original defect: an omitted flag used to be written back as False."""
        client.post("/settings/detection", json={"anonymize_dates": True})

        source = tmp_path / "note.md"
        source.write_text("Ali sent the report.", encoding="utf-8")
        run_client.post("/document/process-file", json={"file_path": str(source)})

        assert user_settings.anonymize_dates is True
