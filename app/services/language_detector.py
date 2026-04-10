import logging
from typing import Final

from langdetect import detect, LangDetectException

logger = logging.getLogger(__name__)

SUPPORTED_LANGUAGES: Final[frozenset[str]] = frozenset({"en", "nl"})
DEFAULT_LANGUAGE: Final[str] = "en"


class LanguageDetector:
    """Detects the primary language of a text string, returning 'en' or 'nl'."""

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
