import logging
import re
from dataclasses import dataclass, field
from typing import Final, Optional

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.services.pattern_config import PatternConfig

logger = logging.getLogger(__name__)

_NLP_CONFIGURATION: Final[dict] = {
    "nlp_engine_name": "spacy",
    "models": [
        {"lang_code": "en", "model_name": "en_core_web_md"},
        {"lang_code": "nl", "model_name": "nl_core_news_md"},
    ],
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
    known_values: list[str], language: str
) -> list[PatternRecognizer]:
    """Return one high-confidence PatternRecognizer per known value.

    Each recognizer matches its value case-insensitively as a whole word and
    assigns entity type PERSON with confidence 0.99. Recognizers are prepended
    before NER so known values are always caught regardless of model detection.
    """
    recognizers: list[PatternRecognizer] = []
    for value in known_values:
        if not value.strip():
            continue
        pattern = Pattern(
            name=f"KNOWN_{re.sub(r'[^A-Z0-9]', '_', value.upper())[:30]}",
            regex=re.escape(value.strip()),
            score=0.99,
        )
        recognizers.append(
            PatternRecognizer(
                supported_entity="PERSON",
                patterns=[pattern],
                supported_language=language,
                context=None,
            )
        )
    return recognizers


class Anonymizer:
    """Detects and replaces PII in text using Presidio with English and Dutch spaCy models."""

    def __init__(self) -> None:
        """Load spaCy models and configure the Presidio analyzer engine."""
        provider = NlpEngineProvider(nlp_configuration=_NLP_CONFIGURATION)
        nlp_engine = provider.create_engine()
        self._analyzer = AnalyzerEngine(
            nlp_engine=nlp_engine,
            supported_languages=["en", "nl"],
        )
        self._analyzer.registry.add_recognizer(DutchBsnRecognizer())

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

        active_entities = entities if entities is not None else ENTITIES

        try:
            results = self._analyzer.analyze(
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
