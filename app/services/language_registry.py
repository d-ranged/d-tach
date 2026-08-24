import logging
import subprocess
import sys
import threading
from dataclasses import dataclass
from typing import Final, Optional

import spacy

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
    """

    def __init__(self, anonymizer: Optional[object] = None) -> None:
        """Initialise, optionally binding the Anonymizer whose loaded state is reported."""
        self._anonymizer = anonymizer
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

    @staticmethod
    def is_installed(code: str) -> bool:
        """Return True if the spaCy model for this language is installed on disk."""
        lang = _BY_CODE.get(code)
        if lang is None:
            return False
        return spacy.util.is_package(lang.spacy_model)

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
    # Install (subprocess `spacy download`, background thread + polled status)
    # ------------------------------------------------------------------

    def download_status(self, code: str) -> dict:
        """Return the current download status for a language: {state, message}.

        state is one of "idle", "downloading", "done", "error".
        """
        return dict(self._download_status.get(code, {"state": "idle", "message": ""}))

    def start_download(self, code: str) -> None:
        """Kick off `python -m spacy download <model>` in a background thread.

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
        """Run the spaCy download subprocess and record the outcome (thread target)."""
        try:
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
    # Remove (pip uninstall, synchronous — fast enough for a request/response)
    # ------------------------------------------------------------------

    def remove(self, code: str) -> None:
        """Uninstall the spaCy model package for this language from disk.

        Raises subprocess.CalledProcessError on failure. Callers are
        responsible for also removing the language from enabled_languages,
        since an uninstalled model can no longer be loaded.
        """
        lang = _BY_CODE.get(code)
        if lang is None:
            raise ValueError(f"Unsupported language code: {code!r}")
        subprocess.run(
            [sys.executable, "-m", "pip", "uninstall", "-y", lang.spacy_model],
            check=True,
            capture_output=True,
            text=True,
        )
        with self._lock:
            self._download_status.pop(code, None)
