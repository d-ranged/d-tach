"""Tests for the LanguageRegistry service class (issue #62)."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from app.services.language_registry import LanguageInfo, LanguageRegistry


class _FakeAnonymizer:
    """Minimal stand-in for Anonymizer, tracking loaded languages in memory."""

    def __init__(self, loaded: list[str] | None = None) -> None:
        self.loaded_languages = list(loaded or ["en"])
        self.ensure_loaded_calls: list[str] = []

    def ensure_loaded(self, code: str) -> None:
        self.ensure_loaded_calls.append(code)
        if code not in self.loaded_languages:
            self.loaded_languages.append(code)


class _SyncThread:
    """Stand-in for threading.Thread that runs its target synchronously."""

    def __init__(self, target=None, args=(), daemon=None) -> None:
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


# ---------------------------------------------------------------------------
# Supported
# ---------------------------------------------------------------------------


class TestSupportedLanguages:
    def test_supported_languages_includes_en_and_nl(self) -> None:
        codes = {lang.code for lang in LanguageRegistry.supported_languages()}
        assert codes == {"en", "nl"}

    def test_info_returns_language_info(self) -> None:
        info = LanguageRegistry.info("nl")
        assert info is not None
        assert info.name == "Dutch"
        assert info.spacy_model == "nl_core_news_md"

    def test_info_returns_none_for_unsupported(self) -> None:
        assert LanguageRegistry.info("xx") is None


# ---------------------------------------------------------------------------
# Installed (real spaCy check — both models are installed in the dev venv)
# ---------------------------------------------------------------------------


class TestInstalled:
    def test_is_installed_true_for_installed_model(self) -> None:
        assert LanguageRegistry().is_installed("en") is True

    def test_is_installed_false_for_unsupported_code(self) -> None:
        assert LanguageRegistry().is_installed("xx") is False

    def test_installed_languages_includes_en(self) -> None:
        registry = LanguageRegistry()
        assert "en" in registry.installed_languages()


# ---------------------------------------------------------------------------
# Loaded (delegates to the bound Anonymizer)
# ---------------------------------------------------------------------------


class TestLoaded:
    def test_loaded_languages_empty_without_anonymizer(self) -> None:
        registry = LanguageRegistry()
        assert registry.loaded_languages() == []

    def test_is_loaded_false_without_anonymizer(self) -> None:
        registry = LanguageRegistry()
        assert registry.is_loaded("en") is False

    def test_loaded_languages_delegates_to_anonymizer(self) -> None:
        fake = _FakeAnonymizer(loaded=["en"])
        registry = LanguageRegistry(anonymizer=fake)
        assert registry.loaded_languages() == ["en"]
        assert registry.is_loaded("en") is True
        assert registry.is_loaded("nl") is False

    def test_set_anonymizer_attaches_instance(self) -> None:
        registry = LanguageRegistry()
        fake = _FakeAnonymizer(loaded=["en"])
        registry.set_anonymizer(fake)
        assert registry.loaded_languages() == ["en"]

    def test_ensure_loaded_without_anonymizer_raises(self) -> None:
        registry = LanguageRegistry()
        with pytest.raises(RuntimeError):
            registry.ensure_loaded("en")

    def test_ensure_loaded_delegates_to_anonymizer(self) -> None:
        fake = _FakeAnonymizer(loaded=["en"])
        registry = LanguageRegistry(anonymizer=fake)
        registry.ensure_loaded("nl")
        assert fake.ensure_loaded_calls == ["nl"]


# ---------------------------------------------------------------------------
# Install / download status
# ---------------------------------------------------------------------------


class TestDownload:
    def test_default_status_is_idle(self) -> None:
        registry = LanguageRegistry()
        assert registry.download_status("nl") == {"state": "idle", "message": ""}

    def test_start_download_unsupported_language_raises(self) -> None:
        registry = LanguageRegistry()
        with pytest.raises(ValueError):
            registry.start_download("xx")

    def test_start_download_success_sets_done_status(self) -> None:
        registry = LanguageRegistry()
        with patch("app.services.language_registry.threading.Thread", _SyncThread), \
             patch("app.services.language_registry.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            registry.start_download("nl")
        assert registry.download_status("nl") == {"state": "done", "message": ""}
        mock_run.assert_called_once()
        assert "nl_core_news_md" in mock_run.call_args[0][0]

    def test_start_download_failure_sets_error_status(self) -> None:
        registry = LanguageRegistry()
        with patch("app.services.language_registry.threading.Thread", _SyncThread), \
             patch("app.services.language_registry.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.CalledProcessError(1, "cmd", stderr="boom")
            registry.start_download("nl")
        status = registry.download_status("nl")
        assert status["state"] == "error"
        assert "boom" in status["message"]

    def test_start_download_noop_when_already_downloading(self) -> None:
        registry = LanguageRegistry()
        registry._download_status["nl"] = {"state": "downloading", "message": ""}
        with patch("app.services.language_registry.threading.Thread") as mock_thread:
            registry.start_download("nl")
        mock_thread.assert_not_called()

    def test_start_download_never_calls_subprocess_for_unsupported(self) -> None:
        registry = LanguageRegistry()
        with patch("app.services.language_registry.subprocess.run") as mock_run:
            with pytest.raises(ValueError):
                registry.start_download("xx")
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------


class TestRemove:
    def test_remove_unsupported_language_raises(self) -> None:
        registry = LanguageRegistry()
        with pytest.raises(ValueError):
            registry.remove("xx")

    def test_remove_calls_pip_uninstall_for_the_right_model(self) -> None:
        registry = LanguageRegistry()
        with patch("app.services.language_registry.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            registry.remove("nl")
        mock_run.assert_called_once()
        command = mock_run.call_args[0][0]
        assert "uninstall" in command
        assert "nl_core_news_md" in command

    def test_remove_clears_download_status(self) -> None:
        registry = LanguageRegistry()
        registry._download_status["nl"] = {"state": "done", "message": ""}
        with patch("app.services.language_registry.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            registry.remove("nl")
        assert registry.download_status("nl") == {"state": "idle", "message": ""}


# ---------------------------------------------------------------------------
# Frozen build: no pip, models go through the ModelStore (issue #79)
# ---------------------------------------------------------------------------


class _FakeStore:
    """Stand-in for ModelStore, recording calls instead of touching disk or network."""

    def __init__(self, installed: set[str] | None = None) -> None:
        self.installed = set(installed or ())
        self.downloaded: list[str] = []
        self.removed: list[str] = []

    def is_installed(self, model: str) -> bool:
        return model in self.installed

    def download(self, model: str) -> None:
        self.downloaded.append(model)
        self.installed.add(model)

    def remove(self, model: str) -> bool:
        self.removed.append(model)
        had = model in self.installed
        self.installed.discard(model)
        return had


@pytest.fixture
def frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    monkeypatch.setattr(sys, "frozen", True, raising=False)


class TestModelStoreIntegration:
    def test_is_installed_asks_the_store(self) -> None:
        registry = LanguageRegistry(model_store=_FakeStore(installed={"nl_core_news_md"}))
        assert registry.is_installed("nl") is True
        assert registry.is_installed("en") is False
        assert registry.installed_languages() == ["nl"]

    def test_frozen_download_uses_the_store_not_pip(self, frozen) -> None:
        store = _FakeStore()
        registry = LanguageRegistry(model_store=store)
        with patch("app.services.language_registry.threading.Thread", _SyncThread), \
             patch("app.services.language_registry.subprocess.run") as mock_run:
            registry.start_download("nl")
        mock_run.assert_not_called()
        assert store.downloaded == ["nl_core_news_md"]
        assert registry.download_status("nl")["state"] == "done"

    def test_frozen_download_failure_sets_error_status(self, frozen) -> None:
        store = _FakeStore()
        store.download = MagicMock(side_effect=OSError("network down"))
        registry = LanguageRegistry(model_store=store)
        with patch("app.services.language_registry.threading.Thread", _SyncThread):
            registry.start_download("nl")
        status = registry.download_status("nl")
        assert status["state"] == "error"
        assert "network down" in status["message"]

    def test_source_download_still_runs_spacy_download(self) -> None:
        store = _FakeStore()
        registry = LanguageRegistry(model_store=store)
        with patch("app.services.language_registry.threading.Thread", _SyncThread), \
             patch("app.services.language_registry.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            registry.start_download("nl")
        command = mock_run.call_args[0][0]
        assert command[1:] == ["-m", "spacy", "download", "nl_core_news_md"]
        assert store.downloaded == []

    def test_frozen_remove_deletes_from_the_store_without_pip(self, frozen) -> None:
        store = _FakeStore(installed={"nl_core_news_md"})
        registry = LanguageRegistry(model_store=store)
        with patch("app.services.language_registry.subprocess.run") as mock_run:
            registry.remove("nl")
        mock_run.assert_not_called()
        assert store.removed == ["nl_core_news_md"]
        assert registry.is_installed("nl") is False

    def test_source_remove_clears_the_store_and_runs_pip(self) -> None:
        store = _FakeStore(installed={"nl_core_news_md"})
        registry = LanguageRegistry(model_store=store)
        with patch("app.services.language_registry.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            registry.remove("nl")
        assert store.removed == ["nl_core_news_md"]
        assert "uninstall" in mock_run.call_args[0][0]
