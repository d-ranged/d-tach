"""Language changes apply without a restart, and modes offer only usable languages.

Found in the frozen-build test of #79: a new language needed a restart, then
"Load on startup", then another restart, and Text Mode offered NL with no Dutch
model installed. These tests run the real create_app with only the model layer
faked, so no spaCy model is loaded.
"""

from unittest.mock import MagicMock, patch

import pytest

from app import APP_ID, __version__, create_app
from app.services.anonymizer import Anonymizer
from app.services.language_registry import LanguageRegistry, pick_language
from app.services.model_store import ModelStore


class _SyncThread:
    """Stand-in for threading.Thread that runs its target synchronously."""

    def __init__(self, target=None, args=(), daemon=None) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


@pytest.fixture
def installed(monkeypatch: pytest.MonkeyPatch) -> set:
    """spaCy model names on 'disk'. Loading a language puts a stand-in in RAM."""
    models = {"en_core_web_md"}
    monkeypatch.setattr(ModelStore, "is_installed", lambda self, model: model in models)
    monkeypatch.setattr(ModelStore, "remove", lambda self, model: models.discard(model) is None)

    def _fake_load(self, language: str) -> None:
        model = {"en": "en_core_web_md", "nl": "nl_core_news_md"}[language]
        if model not in models:
            raise RuntimeError(f"{model} is not installed")
        self._analyzers.setdefault(language, object())

    monkeypatch.setattr(Anonymizer, "_load_language", _fake_load)
    return models


@pytest.fixture
def app(installed: set):
    flask_app = create_app()
    flask_app.user_settings.language_setup_complete = True
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


def _install_dutch(app, installed: set) -> None:
    """Run the source download path synchronously, as if pip had installed nl."""

    def _pip_download(*args, **kwargs):
        installed.add("nl_core_news_md")
        return MagicMock(returncode=0)

    with patch("app.services.language_registry.threading.Thread", _SyncThread), \
         patch("app.services.language_registry.subprocess.run", side_effect=_pip_download):
        app.language_registry.start_download("nl")


class TestPickLanguage:
    def test_keeps_a_usable_preference(self) -> None:
        assert pick_language("nl", ["en", "nl"]) == "nl"

    def test_falls_back_when_the_preference_was_removed(self) -> None:
        assert pick_language("nl", ["en"]) == "en"

    def test_nothing_usable_keeps_the_preference(self) -> None:
        assert pick_language("nl", []) == "nl"


class TestInstallAppliesStraightAway:
    def test_new_language_is_enabled_loaded_and_saved(self, app, installed: set) -> None:
        _install_dutch(app, installed)

        assert app.language_registry.download_status("nl")["state"] == "done"
        assert "nl" in app.user_settings.enabled_languages
        assert "nl" in app.anonymizer.loaded_languages

    def test_lazy_mode_enables_without_loading(self, app, installed: set) -> None:
        app.user_settings.loading_strategy = "lazy"
        _install_dutch(app, installed)

        assert "nl" in app.user_settings.enabled_languages
        assert "nl" not in app.anonymizer.loaded_languages

    def test_failure_after_download_is_reported(self, installed: set) -> None:
        registry = LanguageRegistry()

        def _broken(code: str) -> None:
            raise RuntimeError("could not load")

        registry.set_install_callback(_broken)
        with patch("app.services.language_registry.threading.Thread", _SyncThread), \
             patch("app.services.language_registry.subprocess.run", return_value=MagicMock(returncode=0)):
            registry.start_download("nl")

        assert registry.download_status("nl") == {"state": "error", "message": "could not load"}


class TestToggleAndRemoveApplyStraightAway:
    @pytest.fixture
    def dutch(self, app, installed: set) -> None:
        _install_dutch(app, installed)

    def test_disabling_drops_the_model_from_ram(self, app, client, dutch) -> None:
        response = client.post("/settings/languages/enabled", json={"code": "nl", "enabled": False})

        assert response.status_code == 200
        assert "nl" not in app.anonymizer.loaded_languages
        assert "nl" not in app.user_settings.enabled_languages

    def test_enabling_loads_it_again(self, app, client, dutch) -> None:
        client.post("/settings/languages/enabled", json={"code": "nl", "enabled": False})
        client.post("/settings/languages/enabled", json={"code": "nl", "enabled": True})

        assert "nl" in app.anonymizer.loaded_languages

    def test_remove_unloads_and_deletes(self, app, client, installed: set, dutch) -> None:
        with patch("app.services.language_registry.subprocess.run", return_value=MagicMock(returncode=0)):
            response = client.post("/settings/languages/remove", json={"code": "nl"})

        assert response.status_code == 200
        assert "nl" not in app.anonymizer.loaded_languages
        assert "nl_core_news_md" not in installed

    def test_switching_to_eager_loads_enabled_languages(self, app, client, installed: set) -> None:
        app.user_settings.loading_strategy = "lazy"
        _install_dutch(app, installed)
        assert "nl" not in app.anonymizer.loaded_languages

        client.post("/settings/languages/loading-strategy", json={"strategy": "eager"})

        assert "nl" in app.anonymizer.loaded_languages


class TestModesOfferOnlyUsableLanguages:
    @pytest.mark.parametrize("page", ["/text", "/document"])
    def test_nl_button_is_disabled_without_the_dutch_model(self, client, page: str) -> None:
        html = client.get(page).get_data(as_text=True)

        assert 'data-lang="nl" disabled' in html
        assert 'data-lang="en" disabled' not in html

    @pytest.mark.parametrize("page", ["/text", "/document"])
    def test_nl_button_is_enabled_once_dutch_is_installed(self, app, client, installed: set, page: str) -> None:
        _install_dutch(app, installed)
        html = client.get(page).get_data(as_text=True)

        assert 'data-lang="nl" disabled' not in html

    def test_page_starts_on_a_usable_language(self, app, client) -> None:
        app.user_settings.language = "nl"
        html = client.get("/text").get_data(as_text=True)

        assert 'const INITIAL_LANGUAGE = "en";' in html

    def test_settings_default_language_list_greys_out_dutch(self, client) -> None:
        html = " ".join(client.get("/settings").get_data(as_text=True).split())

        assert '<option value="nl" disabled>' in html
        assert '<option value="en" selected >' in html


class TestPing:
    def test_identifies_d_tach(self, client) -> None:
        assert client.get("/ping").get_json() == {"app": APP_ID, "version": __version__}

    def test_answers_before_language_setup(self, app, client) -> None:
        app.user_settings.language_setup_complete = False
        response = client.get("/ping")

        assert response.status_code == 200
        assert response.get_json()["app"] == APP_ID


class TestAnonymizerUnload:
    def test_unload_reports_whether_anything_was_dropped(self, installed: set) -> None:
        anonymizer = Anonymizer(languages=["en"])

        assert anonymizer.unload("en") is True
        assert anonymizer.loaded_languages == []
        assert anonymizer.unload("en") is False
