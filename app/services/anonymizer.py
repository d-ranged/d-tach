import logging
from dataclasses import dataclass, field
from typing import Final, Optional

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider

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
    "LOCATION",
    "URL",
    "DATE_TIME",
    "IBAN_CODE",
    "NL_BSN",
]


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
    ) -> AnonymizationResult:
        """Replace PII in text with sequential placeholders and return the result.

        Each unique piece of original text maps to one placeholder so the same
        name appearing twice always produces the same replacement within a call.
        Entities are numbered per type: PERSON_1, PERSON_2, EMAIL_ADDRESS_1, etc.

        Pass a custom ``entities`` list to restrict or expand which entity types
        are detected. When None, the default ENTITIES list is used.
        """
        if not text or not text.strip():
            return AnonymizationResult(anonymized_text=text)

        active_entities = entities if entities is not None else ENTITIES

        try:
            results = self._analyzer.analyze(
                text=text,
                language=language,
                entities=active_entities,
            )
        except Exception as exc:
            logger.error("Presidio analysis failed (language=%s): %s", language, exc)
            raise

        if not results:
            return AnonymizationResult(anonymized_text=text)

        counters: dict[str, int] = {}
        placeholder_map: dict[str, str] = {}
        entities: list[DetectedEntity] = []

        for result in sorted(results, key=lambda r: r.start):
            original = text[result.start:result.end]
            if original not in placeholder_map:
                entity_type = result.entity_type
                counters[entity_type] = counters.get(entity_type, 0) + 1
                placeholder_map[original] = f"{entity_type}_{counters[entity_type]}"

            entities.append(DetectedEntity(
                entity_type=result.entity_type,
                start=result.start,
                end=result.end,
                original_text=original,
                placeholder=placeholder_map[original],
            ))

        # Replace from end of string to preserve earlier character positions
        anonymized = text
        for entity in sorted(entities, key=lambda e: e.start, reverse=True):
            anonymized = (
                anonymized[:entity.start]
                + entity.placeholder
                + anonymized[entity.end:]
            )

        return AnonymizationResult(anonymized_text=anonymized, entities=entities)
