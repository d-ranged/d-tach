import logging
from typing import Final, Optional

from langdetect import detect, LangDetectException

from app.services.language_registry import SUPPORTED_LANGUAGE_CODES, LanguageRegistry

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: Final[frozenset[str]] = SUPPORTED_LANGUAGE_CODES
DEFAULT_LANGUAGE: Final[str] = "en"

_LANGUAGE_NAMES: Final[dict[str, str]] = {"en": "English", "nl": "Dutch"}


class LanguageNotLoadedError(Exception):
    """Raised when text needs a language model that is not currently loaded."""

    def __init__(self, language: str) -> None:
        """Build the user-facing error message for the given unloaded language code."""
        name = _LANGUAGE_NAMES.get(language, language)
        self.language = language
        self.message = (
            f"{name} detected but {name} model is not enabled. "
            "Enable it in Settings > Languages."
        )
        super().__init__(self.message)


class LanguageDetector:
    """Detects the primary language of a text string, returning 'en' or 'nl'."""

    def __init__(self, registry: Optional[LanguageRegistry] = None) -> None:
        """Bind the LanguageRegistry consulted by ensure_loaded() before routing text."""
        self._registry = registry

    def detect(self, text: str) -> str:
        """Return the detected language code ('en' or 'nl').

        Falls back to 'en' if the text is empty, detection fails, or the
        detected language is not supported.
        """
        if not text or not text.strip():
            return DEFAULT_LANGUAGE

        try:
            lang = detect(text)
            return lang if lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        except LangDetectException as exc:
            logger.warning("Language detection failed: %s", exc)
            return DEFAULT_LANGUAGE

    def ensure_loaded(self, language: str, loading_strategy: str = "eager") -> None:
        """Make sure a language's model is loaded before routing text to it.

        In 'eager' mode, every enabled language is already loaded at startup —
        if it is not loaded here, that means it is not enabled at all, so this
        raises LanguageNotLoadedError with a clear, user-facing message.

        In 'lazy' mode, an enabled-but-not-yet-loaded language is loaded on
        demand via the registry. LanguageNotLoadedError is still raised if the
        language ends up unavailable (e.g. not installed).
        """
        if self._registry is None:
            return

        if self._registry.is_loaded(language):
            return

        if loading_strategy == "lazy":
            try:
                self._registry.ensure_loaded(language)
                return
            except Exception as exc:
                logger.warning("Lazy load of language %r failed: %s", language, exc)
                raise LanguageNotLoadedError(language) from exc

        raise LanguageNotLoadedError(language)
