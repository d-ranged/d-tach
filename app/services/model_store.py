"""spaCy language models in a per-user folder, so a frozen build needs no pip.

A frozen build has no pip and no site-packages to install into, so models are
fetched as the same wheel ``spacy download`` would install, and only the model
folder inside it is unpacked under the per-user models folder:

    <models_dir>/nl_core_news_md/nl_core_news_md-3.8.0/config.cfg ...

spaCy and Presidio load a model from that folder path. Running from source
still finds pip-installed models first, so the source install works as before.
"""
import logging
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Final, Optional

import spacy

from app import app_paths

logger = logging.getLogger(__name__)

MODEL_CONFIG_FILE: Final[str] = "config.cfg"
PARTIAL_SUFFIX: Final[str] = ".partial"
DOWNLOAD_TIMEOUT_SECONDS: Final[int] = 300
DOWNLOAD_CHUNK_BYTES: Final[int] = 1024 * 1024


class ModelStore:
    """Downloads, finds and removes spaCy models in the per-user models folder."""

    def __init__(self, models_dir: Optional[Path] = None) -> None:
        """Use the given models folder, or the per-user one when omitted."""
        self._models_dir = models_dir

    @property
    def models_dir(self) -> Path:
        """The folder models are unpacked into (resolved on each use)."""
        return self._models_dir if self._models_dir is not None else app_paths.models_dir()

    def model_folder(self, model: str) -> Optional[Path]:
        """Return the unpacked folder for a model, or None if it is not in the store."""
        root = self.models_dir / model
        if not root.is_dir():
            return None
        for child in sorted(root.iterdir(), reverse=True):
            if child.is_dir() and (child / MODEL_CONFIG_FILE).is_file():
                return child
        return None

    def load_target(self, model: str) -> Optional[str]:
        """Return what to pass to ``spacy.load`` for a model, or None if not installed.

        The pip package name when one is installed (source runs), otherwise the
        folder path from the store (frozen builds).
        """
        if spacy.util.is_package(model):
            return model
        folder = self.model_folder(model)
        return str(folder) if folder is not None else None

    def is_installed(self, model: str) -> bool:
        """Return True if the model is installed as a pip package or in the store."""
        return self.load_target(model) is not None

    def download(self, model: str) -> None:
        """Fetch the model wheel matching the bundled spaCy and unpack it into the store.

        The model appears under its final name only once fully unpacked, so a
        half-finished download is never reported as installed.
        """
        version = self._compatible_version(model)
        url = f"{spacy.about.__download_url__}/{model}-{version}/{model}-{version}-py3-none-any.whl"
        self.models_dir.mkdir(parents=True, exist_ok=True)
        target = self.models_dir / model
        partial = self.models_dir / f"{model}{PARTIAL_SUFFIX}"
        shutil.rmtree(partial, ignore_errors=True)

        with tempfile.TemporaryDirectory(dir=self.models_dir) as tmp:
            wheel_path = Path(tmp) / f"{model}.whl"
            self._fetch(url, wheel_path)
            prefix = f"{model}/{model}-{version}/"
            with zipfile.ZipFile(wheel_path) as wheel:
                members = [name for name in wheel.namelist() if name.startswith(prefix)]
                if not members:
                    raise RuntimeError(f"{url} holds no {prefix} folder.")
                wheel.extractall(partial, members)

        shutil.rmtree(target, ignore_errors=True)
        (partial / model).rename(target)
        shutil.rmtree(partial, ignore_errors=True)
        logger.info("Downloaded %s %s into %s.", model, version, target)

    def remove(self, model: str) -> bool:
        """Delete a model from the store. Returns True if there was one to delete."""
        target = self.models_dir / model
        if not target.exists():
            return False
        shutil.rmtree(target)
        logger.info("Removed %s from %s.", model, self.models_dir)
        return True

    @staticmethod
    def _compatible_version(model: str) -> str:
        """Return the model version that matches the installed spaCy, as ``spacy download`` picks it."""
        from spacy.cli.download import get_compatibility, get_version

        return get_version(model, get_compatibility())

    @staticmethod
    def _fetch(url: str, destination: Path) -> None:
        """Stream a URL to a file."""
        import requests

        with requests.get(url, stream=True, timeout=DOWNLOAD_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            with destination.open("wb") as out:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_BYTES):
                    out.write(chunk)
