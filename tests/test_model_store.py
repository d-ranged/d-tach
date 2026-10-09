"""Tests for ModelStore: spaCy models in a per-user folder for frozen builds (issue #79)."""

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app import app_paths
from app.services.model_store import ModelStore

MODEL = "nl_core_news_md"
VERSION = "3.8.0"


def _write_fake_wheel(destination: Path, model: str = MODEL, version: str = VERSION) -> None:
    """Write a wheel laid out like explosion's spacy-models releases."""
    with zipfile.ZipFile(destination, "w") as wheel:
        wheel.writestr(f"{model}/__init__.py", "")
        wheel.writestr(f"{model}/meta.json", "{}")
        wheel.writestr(f"{model}/{model}-{version}/config.cfg", "[nlp]\n")
        wheel.writestr(f"{model}/{model}-{version}/meta.json", "{}")
        wheel.writestr(f"{model}/{model}-{version}/vocab/strings.json", "[]")
        wheel.writestr(f"{model}-{version}.dist-info/METADATA", "")


@pytest.fixture
def store(tmp_path: Path) -> ModelStore:
    return ModelStore(models_dir=tmp_path / "models")


@pytest.fixture
def fake_download():
    """Replace the network: a fixed version and a fake wheel."""
    with patch.object(ModelStore, "_compatible_version", return_value=VERSION) as version, \
         patch.object(ModelStore, "_fetch", side_effect=lambda url, dest: _write_fake_wheel(dest)) as fetch:
        yield version, fetch


class TestModelsDir:
    def test_defaults_to_the_per_user_models_folder(self, isolated_user_data_dir: Path) -> None:
        assert ModelStore().models_dir == isolated_user_data_dir / "models"
        assert ModelStore().models_dir == app_paths.models_dir()

    def test_explicit_folder_wins(self, tmp_path: Path) -> None:
        assert ModelStore(models_dir=tmp_path).models_dir == tmp_path


class TestDownload:
    def test_unpacks_only_the_model_folder(self, store: ModelStore, fake_download) -> None:
        store.download(MODEL)

        folder = store.model_folder(MODEL)
        assert folder == store.models_dir / MODEL / f"{MODEL}-{VERSION}"
        assert (folder / "config.cfg").is_file()
        assert (folder / "vocab" / "strings.json").is_file()
        assert not (store.models_dir / MODEL / "__init__.py").exists()
        assert not any(store.models_dir.glob("*.dist-info"))

    def test_fetches_the_wheel_for_the_compatible_version(self, store: ModelStore, fake_download) -> None:
        _, fetch = fake_download
        store.download(MODEL)
        url = fetch.call_args[0][0]
        assert url.endswith(f"/{MODEL}-{VERSION}/{MODEL}-{VERSION}-py3-none-any.whl")

    def test_leaves_no_partial_or_temp_files(self, store: ModelStore, fake_download) -> None:
        store.download(MODEL)
        assert sorted(p.name for p in store.models_dir.iterdir()) == [MODEL]

    def test_replaces_an_older_copy(self, store: ModelStore, fake_download) -> None:
        old = store.models_dir / MODEL / f"{MODEL}-3.7.0"
        old.mkdir(parents=True)
        (old / "config.cfg").write_text("", encoding="utf-8")

        store.download(MODEL)

        assert not old.exists()
        assert store.model_folder(MODEL).name == f"{MODEL}-{VERSION}"

    def test_failed_fetch_installs_nothing(self, store: ModelStore) -> None:
        with patch.object(ModelStore, "_compatible_version", return_value=VERSION), \
             patch.object(ModelStore, "_fetch", side_effect=OSError("network down")):
            with pytest.raises(OSError):
                store.download(MODEL)
        assert store.model_folder(MODEL) is None
        assert sorted(p.name for p in store.models_dir.iterdir()) == []

    def test_wheel_without_the_model_folder_is_rejected(self, store: ModelStore) -> None:
        with patch.object(ModelStore, "_compatible_version", return_value=VERSION), \
             patch.object(ModelStore, "_fetch", side_effect=lambda url, dest: _write_fake_wheel(dest, version="9.9.9")):
            with pytest.raises(RuntimeError):
                store.download(MODEL)
        assert store.model_folder(MODEL) is None


class TestLoadTarget:
    def test_pip_package_wins_from_source(self, store: ModelStore, fake_download) -> None:
        store.download(MODEL)
        with patch("app.services.model_store.spacy.util.is_package", return_value=True):
            assert store.load_target(MODEL) == MODEL

    def test_folder_path_without_a_pip_package(self, store: ModelStore, fake_download) -> None:
        store.download(MODEL)
        with patch("app.services.model_store.spacy.util.is_package", return_value=False):
            assert store.load_target(MODEL) == str(store.models_dir / MODEL / f"{MODEL}-{VERSION}")
            assert store.is_installed(MODEL) is True

    def test_none_when_installed_nowhere(self, store: ModelStore) -> None:
        with patch("app.services.model_store.spacy.util.is_package", return_value=False):
            assert store.load_target(MODEL) is None
            assert store.is_installed(MODEL) is False

    def test_folder_without_config_does_not_count(self, store: ModelStore) -> None:
        (store.models_dir / MODEL / f"{MODEL}-{VERSION}").mkdir(parents=True)
        assert store.model_folder(MODEL) is None


class TestRemove:
    def test_removes_the_model_folder(self, store: ModelStore, fake_download) -> None:
        store.download(MODEL)
        assert store.remove(MODEL) is True
        assert not (store.models_dir / MODEL).exists()

    def test_nothing_to_remove(self, store: ModelStore) -> None:
        assert store.remove(MODEL) is False


class TestLoadsWithSpacy:
    """A folder in the store is something spaCy can load, as the frozen build does."""

    def test_spacy_loads_a_saved_pipeline_from_the_store(self, store: ModelStore) -> None:
        import spacy

        folder = store.models_dir / MODEL / f"{MODEL}-{VERSION}"
        folder.parent.mkdir(parents=True)
        spacy.blank("nl").to_disk(folder)
        with patch("app.services.model_store.spacy.util.is_package", return_value=False):
            nlp = spacy.load(store.load_target(MODEL))
        assert nlp.lang == "nl"
