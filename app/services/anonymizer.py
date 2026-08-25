import logging
import re
from dataclasses import dataclass, field
from typing import Final, Optional

import spacy
from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.services.pattern_config import PatternConfig

logger = logging.getLogger(__name__)

_MODEL_BY_LANGUAGE: Final[dict[str, str]] = {
    "en": "en_core_web_md",
    "nl": "nl_core_news_md",
}

ENTITIES: Final[list[str]] = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "DATE_TIME",
    "IBAN_CODE",
    "NL_BSN",
]

LOCATION_ENTITY: Final[str] = "LOCATION"

URL_ENTITY: Final[str] = "URL"

NUMERIC_ID_ENTITY: Final[str] = "NUMERIC_ID"

# Matches d-tach's own placeholder syntax so already-anonymized spans are never
# re-detected as new PII on a second pass. Covers both placeholder shapes
# produced by _build_replacements (file_processor.py) / HashEncoder:
#   Sequential: [PERSON_1], [EMAIL_ADDRESS_3], [NUMERIC_ID_2]
#   Hashed name: [Cr-A2T5], [Cr-A2T5 HY23]           (HashEncoder.encode_full_name)
#   Hashed value: [EMAIL_A2B3], [BSN_C4D1], [ID_9F2E]  (HashEncoder.encode_entity)
_PLACEHOLDER_BODY: Final[str] = (
    r"(?:[A-Z][A-Z_]*_\d+"                          # sequential
    r"|[A-Za-z]{1,2}-[A-Z0-9]{4}(?: [A-Z0-9]{4})?"   # hashed name
    r"|[A-Z]+_[A-Z0-9]{4})"                          # hashed value
)
PLACEHOLDER_PATTERN: Final[re.Pattern[str]] = re.compile(rf"\[{_PLACEHOLDER_BODY}\]")


def _is_existing_placeholder(text: str, start: int, end: int) -> bool:
    """True if the detected span at [start:end] is already one of d-tach's placeholders.

    spaCy/Presidio entity spans stop at token boundaries, and square brackets
    always tokenize separately from the content they enclose — so a detected
    span such as a PERSON entity never includes its surrounding '[' and ']'.
    This checks the span together with its immediate neighbouring characters
    rather than the bare span alone, so a placeholder's inner content (e.g.
    'Cr-A2T5 HY23') is still recognized as already-anonymized.
    """
    if start > 0 and end < len(text) and text[start - 1] == "[" and text[end] == "]":
        return bool(PLACEHOLDER_PATTERN.fullmatch(text[start - 1:end + 1]))
    return bool(PLACEHOLDER_PATTERN.fullmatch(text[start:end]))


@dataclass
class DetectedEntity:
    """A single PII entity found in text."""

    entity_type: str
    start: int
    end: int
    original_text: str
    placeholder: str


@dataclass
class AnonymizationResult:
    """The result of an anonymization pass."""

    anonymized_text: str
    entities: list[DetectedEntity] = field(default_factory=list)


class DutchBsnRecognizer(PatternRecognizer):
    """Recognizes Dutch BSN (Burgerservicenummer) via regex and elfproef validation."""

    _PATTERNS: Final[list[Pattern]] = [Pattern("DUTCH_BSN", r"\b\d{9}\b", 0.5)]
    SUPPORTED_ENTITY: Final[str] = "NL_BSN"

    def __init__(self) -> None:
        """Register the BSN pattern for Dutch language."""
        super().__init__(
            supported_entity=self.SUPPORTED_ENTITY,
            patterns=self._PATTERNS,
            supported_language="nl",
        )

    def validate_result(self, pattern_text: str) -> Optional[bool]:
        """Return True if pattern_text passes the Dutch elfproef (11-check)."""
        return self._elfproef(pattern_text)

    @staticmethod
    def _elfproef(bsn: str) -> bool:
        """Return True if the 9-digit string satisfies the Dutch 11-check."""
        if len(bsn) != 9 or not bsn.isdigit():
            return False
        weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
        total = sum(int(d) * w for d, w in zip(bsn, weights))
        return total % 11 == 0


class NumericIdRecognizer(PatternRecognizer):
    """Recognizes fixed-length numeric identifiers (student IDs, employee numbers, etc.).

    Uses the regex from PatternConfig to match the configured digit count and
    excludes sequences immediately preceded by a currency symbol (€, $, £).
    """

    SUPPORTED_ENTITY: Final[str] = NUMERIC_ID_ENTITY

    def __init__(self, pattern_config: PatternConfig, language: str) -> None:
        """Build a recognizer for the given digit count and language.

        Args:
            pattern_config: Active PatternConfig supplying the digit count and regex.
            language: The processing language this recognizer should be registered for.
        """
        regex = pattern_config.build_numeric_id_regex()
        super().__init__(
            supported_entity=self.SUPPORTED_ENTITY,
            patterns=[Pattern("NUMERIC_ID", regex, 0.85)],
            supported_language=language,
        )


def build_numeric_id_recognizer(
    pattern_config: PatternConfig, language: str
) -> NumericIdRecognizer:
    """Return a NumericIdRecognizer configured for the given language."""
    return NumericIdRecognizer(pattern_config, language)


def build_known_value_recognizers(
    known_values: list[dict], language: str
) -> list[PatternRecognizer]:
    """Return one high-confidence PatternRecognizer per known value.

    Each known_values entry is a dict {"value": str, "entity_type": str, ...}.
    Each recognizer matches its value case-insensitively as a whole word and
    assigns its entry's entity_type (default PERSON) with confidence 0.99.
    Recognizers are prepended before NER so known values are always caught
    regardless of model detection.
    """
    recognizers: list[PatternRecognizer] = []
    for entry in known_values:
        value = str(entry.get("value", "")).strip()
        if not value:
            continue
        entity_type = str(entry.get("entity_type") or "PERSON")
        # Lookarounds rather than word-boundary escapes: they behave correctly
        # even when the value starts or ends with a non-word character. Without
        # them a short known value such as "An" matches inside "Thank", "and"
        # and "standard", corrupting ordinary words throughout the document.
        pattern = Pattern(
            name=f"KNOWN_{re.sub(r'[^A-Z0-9]', '_', value.upper())[:30]}",
            regex=rf"(?<!\w){re.escape(value)}(?!\w)",
            score=0.99,
        )
        recognizers.append(
            PatternRecognizer(
                supported_entity=entity_type,
                patterns=[pattern],
                supported_language=language,
                context=None,
            )
        )
    return recognizers


class Anonymizer:
    """Detects and replaces PII in text using Presidio, one spaCy model per language.

    Each supported language gets its own AnalyzerEngine, built lazily so RAM
    is only spent on languages actually in use (see LanguageRegistry / the
    'eager' vs 'lazy' loading strategy in UserSettings).
    """

    def __init__(self, languages: Optional[list[str]] = None) -> None:
        """Load the given languages now (default: all supported languages).

        Pass an empty list to start with nothing loaded (pure lazy mode) or a
        specific subset to load only those. Raises RuntimeError if a requested
        language's spaCy model is not installed — this never triggers an
        implicit download.
        """
        self._analyzers: dict[str, AnalyzerEngine] = {}
        target_languages = languages if languages is not None else list(_MODEL_BY_LANGUAGE.keys())
        for code in target_languages:
            self._load_language(code)

    def _load_language(self, language: str) -> None:
        """Build and cache the AnalyzerEngine for one language, if not already loaded."""
        if language in self._analyzers:
            return

        model_name = _MODEL_BY_LANGUAGE.get(language)
        if model_name is None:
            raise ValueError(f"Unsupported language: {language!r}")

        if not spacy.util.is_package(model_name):
            raise RuntimeError(
                f"The {language!r} language model ({model_name}) is not installed. "
                "Install it in Settings > Languages."
            )

        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": language, "model_name": model_name}],
        }
        provider = NlpEngineProvider(nlp_configuration=configuration)
        nlp_engine = provider.create_engine()
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=[language])
        if language == "nl":
            analyzer.registry.add_recognizer(DutchBsnRecognizer())
        self._analyzers[language] = analyzer

    def ensure_loaded(self, language: str) -> None:
        """Load the given language's model into RAM now, if not already loaded."""
        self._load_language(language)

    @property
    def loaded_languages(self) -> list[str]:
        """Codes of every language currently loaded into RAM."""
        return list(self._analyzers.keys())

    def anonymize(
        self,
        text: str,
        language: str,
        entities: Optional[list[str]] = None,
        ad_hoc_recognizers: Optional[list[PatternRecognizer]] = None,
    ) -> AnonymizationResult:
        """Replace PII in text with sequential placeholders and return the result.

        Each unique piece of original text maps to one placeholder so the same
        name appearing twice always produces the same replacement within a call.
        Entities are numbered per type: PERSON_1, PERSON_2, EMAIL_ADDRESS_1, etc.

        Pass a custom ``entities`` list to restrict or expand which entity types
        are detected. When None, the default ENTITIES list is used.

        Pass ``ad_hoc_recognizers`` to add per-request recognizers (e.g. a
        NumericIdRecognizer built from the current PatternConfig) without
        modifying the shared analyzer registry.
        """
        if not text or not text.strip():
            return AnonymizationResult(anonymized_text=text)

        analyzer = self._analyzers.get(language)
        if analyzer is None:
            raise ValueError(
                f"Language {language!r} is not loaded. Call ensure_loaded() first."
            )

        active_entities = entities if entities is not None else ENTITIES

        try:
            results = analyzer.analyze(
                text=text,
                language=language,
                entities=active_entities,
                ad_hoc_recognizers=ad_hoc_recognizers or [],
            )
        except Exception as exc:
            logger.error("Presidio analysis failed (language=%s): %s", language, exc)
            raise

        if not results:
            return AnonymizationResult(anonymized_text=text)

        # Drop any entity types not in the requested list (Presidio may pass through
        # spaCy NER labels like CARDINAL that are not mapped to Presidio entities;
        # keeping them allows them to block legitimate pattern-based detections).
        active_set = set(active_entities)
        results = [r for r in results if r.entity_type in active_set]

        # Drop spans that are already one of d-tach's own placeholders, so
        # re-running anonymize() on already-anonymized text (or text containing
        # a mix of real and already-anonymized values) leaves those spans
        # untouched instead of wrapping or re-tagging them.
        results = [
            r for r in results
            if not _is_existing_placeholder(text, r.start, r.end)
        ]

        results = self._resolve_overlaps(results)

        counters: dict[str, int] = {}
        placeholder_map: dict[str, str] = {}
        detected: list[DetectedEntity] = []

        for result in sorted(results, key=lambda r: r.start):
            original = text[result.start:result.end]
            if original not in placeholder_map:
                entity_type = result.entity_type
                counters[entity_type] = counters.get(entity_type, 0) + 1
                placeholder_map[original] = f"[{entity_type}_{counters[entity_type]}]"

            detected.append(DetectedEntity(
                entity_type=result.entity_type,
                start=result.start,
                end=result.end,
                original_text=original,
                placeholder=placeholder_map[original],
            ))

        # Replace from end of string to preserve earlier character positions
        anonymized = text
        for entity in sorted(detected, key=lambda e: e.start, reverse=True):
            anonymized = (
                anonymized[:entity.start]
                + entity.placeholder
                + anonymized[entity.end:]
            )

        return AnonymizationResult(anonymized_text=anonymized, entities=detected)

    @staticmethod
    def _resolve_overlaps(results: list) -> list:
        """Remove lower-confidence duplicates when NUMERIC_ID overlaps another entity.

        When numeric ID detection is active with a digit count matching a phone
        number length, Presidio fires both NUMERIC_ID and PHONE_NUMBER on the
        same span. This resolver keeps only the higher-confidence detection for
        any overlapping spans — but only when NUMERIC_ID is actually present in
        results, so it has no effect on normal processing without numeric ID enabled.
        """
        if not any(r.entity_type == NUMERIC_ID_ENTITY for r in results):
            return results

        sorted_by_conf = sorted(results, key=lambda r: r.score, reverse=True)
        accepted: list = []
        for result in sorted_by_conf:
            if not any(r.start < result.end and result.start < r.end for r in accepted):
                accepted.append(result)
        return accepted
