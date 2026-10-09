import logging
import re
from dataclasses import dataclass, field
from typing import Final, Optional

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.services.model_store import ModelStore
from app.services.name_rules import RULE_ANY, RULE_SHORT, classify_name, lone_name_pattern
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

PERSON_ENTITY: Final[str] = "PERSON"

LONE_FIRST_NAME_SCORE: Final[float] = 0.85

URL_ENTITY: Final[str] = "URL"

NUMERIC_ID_ENTITY: Final[str] = "NUMERIC_ID"

# Matches d-tach's own placeholder syntax so already-anonymized spans are never
# re-detected as new PII on a second pass. Covers both placeholder shapes
# produced by _build_replacements (file_processor.py) / HashEncoder:
#   Sequential: [PERSON_1], [EMAIL_ADDRESS_3], [NUMERIC_ID_2]
#   Hashed name: [Cr-A2T5], [Cr-A2T5 HY23]           (HashEncoder.encode_full_name)
#                [Cr-A2T5_HY23] is the same name as it reads in a file name,
#                where spaces become underscores
#   Hashed value: [EMAIL_A2B3], [BSN_C4D1], [ID_9F2E]  (HashEncoder.encode_entity)
_PLACEHOLDER_BODY: Final[str] = (
    r"(?:[A-Z][A-Z_]*_\d+"                          # sequential
    r"|[A-Za-z]{1,2}-[A-Z0-9]{4}(?:[ _][A-Z0-9]{4})?"  # hashed name
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


def _strip_possessive(word: str) -> str:
    """Return word without a trailing possessive suffix such as 's."""
    for suffix in _POSSESSIVE_SUFFIXES:
        if word.endswith(suffix) and len(word) > len(suffix):
            return word[:-len(suffix)]
    return word


def _overlaps_placeholder(spans: list[tuple[int, int]], start: int, end: int) -> bool:
    """True if [start:end] touches any of the placeholder spans.

    NER sometimes tags only a piece of a placeholder ('Lo-NUSA 0W3X' without its
    brackets, or the brackets plus a neighbouring word). Wrapping that piece
    again corrupts the placeholder, so any overlap counts, not just an exact hit.
    """
    return any(p_start < end and start < p_end for p_start, p_end in spans)


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
    """Return one high-confidence PatternRecognizer per entity type.

    Each known_values entry is a dict {"value": str, "entity_type": str, ...}.
    Values are matched as whole words and assigned their entry's entity_type
    (default PERSON) with confidence 0.99. An entry's "rule" (see name_rules)
    says how: "any" (the default) case-insensitively, "capital" only with a
    capital first letter, "short" never. Recognizers are
    prepended before NER so known values are always caught regardless of model
    detection.

    All values sharing an entity type are combined into a single alternation
    rather than getting a recognizer each. A class list of 500 students expands
    to well over a thousand known values, and a thousand recognizers means a
    thousand separate passes over every document. Grouping keeps that to one
    pass per entity type.
    """
    values_by_entity: dict[str, list[tuple[str, str]]] = {}
    seen: set[tuple[str, str, str]] = set()
    for entry in known_values:
        value = str(entry.get("value", "")).strip()
        if not value:
            continue
        rule = entry.get("rule") or RULE_ANY
        if rule == RULE_SHORT:
            # Two letters or fewer never match alone ("an", "En", "El"); the
            # name is still caught inside the full name, which is its own entry.
            continue
        entity_type = str(entry.get("entity_type") or "PERSON")
        # Same value and rule differing only in case are duplicates and would
        # otherwise bloat the alternation.
        key = (entity_type, value.lower(), rule)
        if key in seen:
            continue
        seen.add(key)
        pattern_body = lone_name_pattern(value, rule)
        if pattern_body is not None:
            values_by_entity.setdefault(entity_type, []).append((value, pattern_body))

    recognizers: list[PatternRecognizer] = []
    for entity_type, values in values_by_entity.items():
        # Longest first: alternation returns the first branch that matches, so
        # without this "An" would win over "An Nguyen" and leave the surname.
        values.sort(key=lambda item: len(item[0]), reverse=True)
        alternation = "|".join(body for _, body in values)
        # Lookarounds rather than word-boundary escapes: they behave correctly
        # even when the value starts or ends with a non-word character. Without
        # them a short known value such as "An" matches inside "Thank", "and"
        # and "standard", corrupting ordinary words throughout the document.
        pattern = Pattern(
            name=f"KNOWN_{entity_type}",
            regex=rf"(?<!\w)(?:{alternation})(?!\w)",
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



# Longest first: "'s" must be tried before a bare "'", or the s would be kept.
# Both the straight and the typographic apostrophe appear in real documents —
# Word autocorrects to the typographic one, and PDF extraction returns it too.
_NAME_ENTITIES: Final[frozenset[str]] = frozenset({"PERSON", LOCATION_ENTITY})

_POSSESSIVE_SUFFIXES = ("'s", "\u2019s", "'S", "\u2019S", "'", "\u2019")


class Anonymizer:
    """Detects and replaces PII in text using Presidio, one spaCy model per language.

    Each supported language gets its own AnalyzerEngine, built lazily so RAM
    is only spent on languages actually in use (see LanguageRegistry / the
    'eager' vs 'lazy' loading strategy in UserSettings).
    """

    def __init__(self, languages: Optional[list[str]] = None, model_store: Optional[ModelStore] = None) -> None:
        """Load the given languages now (default: all supported languages).

        Pass an empty list to start with nothing loaded (pure lazy mode) or a
        specific subset to load only those. Raises RuntimeError if a requested
        language's spaCy model is not installed — this never triggers an
        implicit download.
        """
        self._analyzers: dict[str, AnalyzerEngine] = {}
        self._model_store = model_store if model_store is not None else ModelStore()
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

        # A package name from source, a folder path in a frozen build. Presidio
        # passes either to spacy.load and skips its own download when it loads.
        load_target = self._model_store.load_target(model_name)
        if load_target is None:
            raise RuntimeError(
                f"The {language!r} language model ({model_name}) is not installed. "
                "Install it in Settings > Languages."
            )

        configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": language, "model_name": load_target}],
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

    def unload(self, language: str) -> bool:
        """Drop a language's model from RAM. Returns False if it was not loaded."""
        return self._analyzers.pop(language, None) is not None

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
        placeholder_spans = [m.span() for m in PLACEHOLDER_PATTERN.finditer(text)]
        results = [
            r for r in results
            if not _is_existing_placeholder(text, r.start, r.end)
            and not _overlaps_placeholder(placeholder_spans, r.start, r.end)
        ]

        results = self._trim_at_line_break(results, text)
        results = self._trim_possessive(results, text)
        results = self._resolve_overlaps(results)
        results = results + self._lone_first_names(results, text, placeholder_spans)

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
    def _trim_at_line_break(results: list, text: str) -> list:
        """Cut a name span at its first line break and drop it if nothing is left.

        spaCy treats a newline as ordinary whitespace, so in a signature such as
        "Joris van Dijk\nGuide" the PERSON span runs on into the next line and
        swallows "Guide" together with the break. A name never spans lines, so
        PERSON and LOCATION spans stop at the first \n or \r and the rest of the
        text stays where it was. Other entity types are left alone: an IBAN or
        phone number is matched by pattern, not by a model guessing at a span.
        """
        trimmed: list = []
        for result in results:
            if result.entity_type in _NAME_ENTITIES:
                span = text[result.start:result.end]
                cut = next((i for i, ch in enumerate(span) if ch in "\r\n"), None)
                if cut is not None:
                    result.end = result.start + len(span[:cut].rstrip())
                    if result.end <= result.start:
                        continue
            trimmed.append(result)
        return trimmed

    @staticmethod
    def _trim_possessive(results: list, text: str) -> list:
        """Shrink a span so a trailing possessive stays in the text, not in the value.

        spaCy hands back "Vandenberg's" as the PERSON span, apostrophe and s
        included, so the possessive ends up inside the value that gets hashed.
        The same person then encodes to one token where their name is possessive
        and another where it is not — and to a third if the apostrophe happens to
        be typographic rather than straight, since the bytes differ and so does
        the hash. An agent reading a folder sees three people instead of one.

        Keeping the same subject on one token across every document is the whole
        point of hashing, so the suffix is trimmed off the span before the value
        is taken. The apostrophe and s stay in the output text, where they belong:
        "[Ma-EJIN CX66]'s report", not "[Ma-EJIN MW5H] report".

        Runs before overlap resolution so a possessive NER span and a plain
        known-value match of the same name compare on equal terms.
        """
        for result in results:
            span = text[result.start:result.end]
            for suffix in _POSSESSIVE_SUFFIXES:
                if span.endswith(suffix) and len(span) > len(suffix):
                    result.end -= len(suffix)
                    break
        return results

    @staticmethod
    def _lone_first_names(
        results: list,
        text: str,
        placeholder_spans: list[tuple[int, int]],
    ) -> list:
        """Find the first word of every replaced full name standing alone in the same text.

        NER sometimes misses a lone first name ("Lotte is on track.") even though
        the full name ("Lotte Vermeulen") is replaced a few lines higher. One
        anonymize() call is one document, so searching this text only keeps the
        match inside the document. The rule for the first word is the one class
        list import uses (name_rules.classify_name): under 3 letters is never
        matched alone, an ordinary word only with a capital, anything else
        however it is written. A match that overlaps an accepted result or an
        existing placeholder is dropped, so a full name is never split.
        """
        first_names: set[str] = set()
        for result in results:
            words = text[result.start:result.end].split()
            if result.entity_type == PERSON_ENTITY and len(words) > 1:
                first_names.add(_strip_possessive(words[0]))
        taken = [(r.start, r.end) for r in results] + placeholder_spans
        found: list = []
        for first in sorted(first_names):
            body = lone_name_pattern(first, classify_name(first))
            if body is None:
                continue
            pattern = re.compile(rf"(?<!\w)(?:{body})(?!\w)", re.IGNORECASE)
            for match in pattern.finditer(text):
                if _overlaps_placeholder(taken, match.start(), match.end()):
                    continue
                found.append(RecognizerResult(
                    entity_type=PERSON_ENTITY,
                    start=match.start(),
                    end=match.end(),
                    score=LONE_FIRST_NAME_SCORE,
                ))
        return found

    @staticmethod
    def _resolve_overlaps(results: list) -> list:
        """Keep one detection per overlapping span, preferring the widest.

        Two recognizers routinely fire on overlapping spans:

        - A known value and NER on the same name. A surname-only roster makes
          this the normal case rather than the exception: NER reports "Din
          Bakker" while the known value reports "Bakker".
        - NUMERIC_ID and PHONE_NUMBER, when the configured digit count matches
          a phone number length.

        Left unresolved, both spans get replaced and the output is corrupted —
        "Din Bakker" came out as "[PERSON_1]N_2]", which no restore pass can
        map back.

        The widest span wins, with confidence as the tie-break. Preferring the
        wider span rather than the higher score matters: a known value scores
        0.99 and NER around 0.85, so scoring first would let a surname-only
        roster shrink every full name down to its surname and leave the first
        name standing in text NER had already covered. Anonymizing more than
        strictly needed is the safe direction to err in; anonymizing less is not.
        """
        ordered = sorted(
            results,
            # Start position last, purely so the result is deterministic when
            # two spans are the same width and score.
            key=lambda r: (r.end - r.start, r.score, -r.start),
            reverse=True,
        )
        accepted: list = []
        for result in ordered:
            if not any(r.start < result.end and result.start < r.end for r in accepted):
                accepted.append(result)
        return accepted
