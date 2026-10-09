import logging
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Final, Optional

from app.app_paths import is_frozen
from app.services.model_store import ModelStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LanguageInfo:
    """Static metadata about one language d-tach has recognizer support for."""

    code: str
    name: str
    spacy_model: str
    download_size_mb: int


SUPPORTED_LANGUAGES: Final[list[LanguageInfo]] = [
    LanguageInfo(code="en", name="English", spacy_model="en_core_web_md", download_size_mb=45),
    LanguageInfo(code="nl", name="Dutch", spacy_model="nl_core_news_md", download_size_mb=45),
]

SUPPORTED_LANGUAGE_CODES: Final[frozenset[str]] = frozenset(lang.code for lang in SUPPORTED_LANGUAGES)

_BY_CODE: Final[dict[str, LanguageInfo]] = {lang.code: lang for lang in SUPPORTED_LANGUAGES}


class LanguageRegistry:
    """Central authority for supported/installed/loaded language state.

    Wraps three independent states per language: Supported (recognizer rules
    exist in the codebase — see SUPPORTED_LANGUAGES), Installed (the spaCy
    model is on disk), and Loaded (the model is in RAM for the running
    Anonymizer). All language-state decisions should go through this class
    rather than inspecting spaCy model availability directly.

    Installed means a pip package (source runs) or a folder in the per-user
    ModelStore (frozen builds, which have no pip).
    """

    def __init__(self, anonymizer: Optional[object] = None, model_store: Optional[ModelStore] = None) -> None:
        """Initialise, optionally binding the Anonymizer whose loaded state is reported."""
        self._anonymizer = anonymizer
        self._model_store = model_store if model_store is not None else ModelStore()
        self._download_status: dict[str, dict] = {}
        self._lock = threading.Lock()

    def set_anonymizer(self, anonymizer: object) -> None:
        """Attach (or replace) the Anonymizer instance used to report loaded state."""
        self._anonymizer = anonymizer

    # ------------------------------------------------------------------
    # Supported
    # ------------------------------------------------------------------

    @staticmethod
    def supported_languages() -> list[LanguageInfo]:
        """Return metadata for every language d-tach has recognizer support for."""
        return list(SUPPORTED_LANGUAGES)

    @staticmethod
    def info(code: str) -> Optional[LanguageInfo]:
        """Return LanguageInfo for a language code, or None if unsupported."""
        return _BY_CODE.get(code)

    # ------------------------------------------------------------------
    # Installed (disk)
    # ------------------------------------------------------------------

    def is_installed(self, code: str) -> bool:
        """Return True if the spaCy model for this language is installed on disk."""
        lang = _BY_CODE.get(code)
        if lang is None:
            return False
        return self._model_store.is_installed(lang.spacy_model)

    def installed_languages(self) -> list[str]:
        """Return codes of every supported language whose model is installed."""
        return [lang.code for lang in SUPPORTED_LANGUAGES if self.is_installed(lang.code)]

    # ------------------------------------------------------------------
    # Loaded (RAM, current session)
    # ------------------------------------------------------------------

    def loaded_languages(self) -> list[str]:
        """Return codes of every language currently loaded in the running Anonymizer."""
        if self._anonymizer is None:
            return []
        return list(self._anonymizer.loaded_languages)

    def is_loaded(self, code: str) -> bool:
        """Return True if the given language's model is currently in RAM."""
        return code in self.loaded_languages()

    def ensure_loaded(self, code: str) -> None:
        """Load the given language's model into the running Anonymizer now (lazy mode).

        Raises RuntimeError if no Anonymizer is attached, or if the model is
        not installed on disk — this never triggers an implicit download.
        """
        if self._anonymizer is None:
            raise RuntimeError("LanguageRegistry has no Anonymizer attached.")
        self._anonymizer.ensure_loaded(code)

    # ------------------------------------------------------------------
    # Install (background thread + polled status): `spacy download` from
    # source, ModelStore.download in a frozen build
    # ------------------------------------------------------------------

    def download_status(self, code: str) -> dict:
        """Return the current download status for a language: {state, message}.

        state is one of "idle", "downloading", "done", "error".
        """
        return dict(self._download_status.get(code, {"state": "idle", "message": ""}))

    def start_download(self, code: str) -> None:
        """Start downloading this language's model in a background thread.

        From source this runs `python -m spacy download <model>`. Frozen,
        `sys.executable` is d-tach itself and there is no pip, so the model is
        unpacked into the ModelStore instead.

        No-op if a download for this language is already in progress. Progress
        is not parsed from pip's output (no reliable percentage is exposed by
        spaCy's downloader) — callers poll download_status() for idle/
        downloading/done/error instead.
        """
        lang = _BY_CODE.get(code)
        if lang is None:
            raise ValueError(f"Unsupported language code: {code!r}")

        with self._lock:
            if self._download_status.get(code, {}).get("state") == "downloading":
                return
            self._download_status[code] = {"state": "downloading", "message": ""}

        thread = threading.Thread(target=self._run_download, args=(lang,), daemon=True)
        thread.start()

    def _run_download(self, lang: LanguageInfo) -> None:
        """Run the download and record the outcome (thread target)."""
        try:
            if is_frozen():
                self._model_store.download(lang.spacy_model)
            else:
                subprocess.run(
                    [sys.executable, "-m", "spacy", "download", lang.spacy_model],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            with self._lock:
                self._download_status[lang.code] = {"state": "done", "message": ""}
        except subprocess.CalledProcessError as exc:
            logger.error("Failed to download %s: %s", lang.spacy_model, exc.stderr)
            with self._lock:
                self._download_status[lang.code] = {
                    "state": "error",
                    "message": (exc.stderr or str(exc)).strip()[-300:],
                }
        except Exception as exc:
            logger.error("Unexpected error downloading %s: %s", lang.spacy_model, exc)
            with self._lock:
                self._download_status[lang.code] = {"state": "error", "message": str(exc)}

    # ------------------------------------------------------------------
    # Remove (synchronous — fast enough for a request/response)
    # ------------------------------------------------------------------

    def remove(self, code: str) -> None:
        """Remove this language's spaCy model from disk.

        Deletes the ModelStore copy if there is one. From source it then runs
        `pip uninstall` as before; a frozen build has no pip and needs nothing
        more. Raises subprocess.CalledProcessError or OSError on failure.
        Callers are responsible for also removing the language from
        enabled_languages, since a removed model can no longer be loaded.
        """
        lang = _BY_CODE.get(code)
        if lang is None:
            raise ValueError(f"Unsupported language code: {code!r}")
        self._model_store.remove(lang.spacy_model)
        if not is_frozen():
            subprocess.run(
                [sys.executable, "-m", "pip", "uninstall", "-y", lang.spacy_model],
                check=True,
                capture_output=True,
                text=True,
            )
        with self._lock:
            self._download_status.pop(code, None)
