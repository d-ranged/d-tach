"""Tests for LanguageDetector and Anonymizer service classes."""

import pytest

from presidio_analyzer import Pattern, PatternRecognizer

from app.services.anonymizer import Anonymizer, AnonymizationResult, DutchBsnRecognizer, ENTITIES, URL_ENTITY
from app.services.language_detector import LanguageDetector, LanguageNotLoadedError


# ---------------------------------------------------------------------------
# Shared fixtures (session-scoped so models load only once per test run)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anonymizer() -> Anonymizer:
    """Single Anonymizer instance shared across all tests."""
    return Anonymizer()


@pytest.fixture(scope="session")
def detector() -> LanguageDetector:
    """Single LanguageDetector instance shared across all tests."""
    return LanguageDetector()


# ---------------------------------------------------------------------------
# LanguageDetector tests
# ---------------------------------------------------------------------------


class TestLanguageDetector:
    def test_english_detected(self, detector: LanguageDetector) -> None:
        lang = detector.detect(
            "The quick brown fox jumps over the lazy dog. "
            "She works as a software engineer in London."
        )
        assert lang == "en"

    def test_dutch_detected(self, detector: LanguageDetector) -> None:
        lang = detector.detect(
            "De snelle bruine vos springt over de luie hond. "
            "Hij werkt als ingenieur in Amsterdam."
        )
        assert lang == "nl"

    def test_empty_string_returns_default(self, detector: LanguageDetector) -> None:
        assert detector.detect("") == "en"

    def test_whitespace_returns_default(self, detector: LanguageDetector) -> None:
        assert detector.detect("   ") == "en"


# ---------------------------------------------------------------------------
# DutchBsnRecognizer elfproef unit tests
# ---------------------------------------------------------------------------


class TestDutchBsnRecognizer:
    def test_valid_bsn_passes(self) -> None:
        # 111222333: sum = 66, 66 % 11 == 0
        assert DutchBsnRecognizer._elfproef("111222333") is True

    def test_invalid_bsn_fails(self) -> None:
        # 123456789: sum = 147, 147 % 11 != 0
        assert DutchBsnRecognizer._elfproef("123456789") is False

    def test_non_digit_string_fails(self) -> None:
        assert DutchBsnRecognizer._elfproef("12345678a") is False

    def test_wrong_length_fails(self) -> None:
        assert DutchBsnRecognizer._elfproef("12345678") is False


# ---------------------------------------------------------------------------
# Anonymizer tests
# ---------------------------------------------------------------------------


class TestAnonymizer:
    def test_english_name_detected_and_replaced(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "My name is John Smith and I live in New York.", "en"
        )
        assert "John Smith" not in result.anonymized_text
        assert any(e.entity_type == "PERSON" for e in result.entities)

    def test_dutch_name_detected_and_replaced(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Jan de Vries woont in Amsterdam en werkt als ingenieur bij een groot bedrijf.",
            "nl",
        )
        assert "Jan de Vries" not in result.anonymized_text
        assert any(e.entity_type == "PERSON" for e in result.entities)

    def test_email_detected_and_replaced(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Please send your report to john.doe@example.com by Friday.", "en"
        )
        assert "john.doe@example.com" not in result.anonymized_text
        assert any(e.entity_type == "EMAIL_ADDRESS" for e in result.entities)

    def test_phone_number_detected_and_replaced(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "You can reach me on +31 6 12345678 between nine and five.", "nl"
        )
        assert "+31 6 12345678" not in result.anonymized_text
        assert any(e.entity_type == "PHONE_NUMBER" for e in result.entities)

    def test_dutch_bsn_detected_and_replaced(self, anonymizer: Anonymizer) -> None:
        # 111222333 is a valid BSN: elfproef sum = 66, 66 % 11 == 0
        result = anonymizer.anonymize("Mijn BSN is 111222333.", "nl")
        assert "111222333" not in result.anonymized_text
        assert any(e.entity_type == "NL_BSN" for e in result.entities)

    def test_clean_text_returned_unchanged(self, anonymizer: Anonymizer) -> None:
        text = "The calculation showed an improvement of fifteen percent."
        result = anonymizer.anonymize(text, "en")
        assert isinstance(result, AnonymizationResult)
        assert result.anonymized_text == text
        assert result.entities == []

    def test_empty_text_returned_as_is(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize("", "en")
        assert result.anonymized_text == ""
        assert result.entities == []

    def test_same_name_gets_same_placeholder(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "John Smith called. Please call John Smith back.", "en"
        )
        occurrences = [e for e in result.entities if e.original_text == "John Smith"]
        if len(occurrences) > 1:
            placeholders = {e.placeholder for e in occurrences}
            assert len(placeholders) == 1

    def test_multiple_entity_types_numbered_independently(
        self, anonymizer: Anonymizer
    ) -> None:
        result = anonymizer.anonymize(
            "Alice wrote to bob@example.com and charlie@example.com.", "en"
        )
        email_placeholders = [
            e.placeholder for e in result.entities if e.entity_type == "EMAIL_ADDRESS"
        ]
        assert "[EMAIL_ADDRESS_1]" in email_placeholders
        if len(email_placeholders) > 1:
            assert "[EMAIL_ADDRESS_2]" in email_placeholders

    def test_result_type_is_correct(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize("Hello world.", "en")
        assert isinstance(result, AnonymizationResult)
        assert isinstance(result.anonymized_text, str)
        assert isinstance(result.entities, list)


class TestUrlEntityDefault:
    def test_url_not_in_default_entities(self) -> None:
        assert URL_ENTITY not in ENTITIES

    def test_url_entity_constant_is_url(self) -> None:
        assert URL_ENTITY == "URL"

    def test_email_not_garbled_without_url_detection(
        self, anonymizer: Anonymizer
    ) -> None:
        """Email-only detection must not consume surrounding text when URL is off."""
        text = "Email: alice@example.com Phone: +44 7911 123456"
        result = anonymizer.anonymize(text, "en", entities=list(ENTITIES))
        assert "[EMAIL_ADDRESS_1]" in result.anonymized_text
        assert "Phone:" in result.anonymized_text

    def test_url_detected_when_explicitly_included(
        self, anonymizer: Anonymizer
    ) -> None:
        entities_with_url = list(ENTITIES) + [URL_ENTITY]
        result = anonymizer.anonymize("Visit www.example.com today.", "en", entities=entities_with_url)
        url_entities = [e for e in result.entities if e.entity_type == "URL"]
        assert len(url_entities) > 0


# ---------------------------------------------------------------------------
# Placeholder-recognition guard — no double-anonymization (issue #64)
# ---------------------------------------------------------------------------


class TestPlaceholderGuard:
    def test_second_pass_is_idempotent(self, anonymizer: Anonymizer) -> None:
        """Running anonymize() on its own output must not change it further."""
        first = anonymizer.anonymize(
            "John Smith emailed sarah@example.com about the report.", "en"
        )
        second = anonymizer.anonymize(first.anonymized_text, "en")
        assert second.anonymized_text == first.anonymized_text
        assert second.entities == []

    def test_sequential_placeholder_not_re_detected(self, anonymizer: Anonymizer) -> None:
        text = "Please forward this file to [PERSON_1] for review."
        result = anonymizer.anonymize(text, "en")
        assert result.anonymized_text == text
        assert result.entities == []

    def test_hashed_name_placeholder_not_re_tagged_as_person(
        self, anonymizer: Anonymizer
    ) -> None:
        """A hashed placeholder must never be re-tagged as a new PERSON.

        Uses a forced ad-hoc recognizer so the test does not depend on
        whether the spaCy model happens to mistag this particular string —
        the guard must hold even when something *would* otherwise match.
        """
        force_person = PatternRecognizer(
            supported_entity="PERSON",
            patterns=[Pattern("FORCE_PERSON", r"Cr-A2T5 HY23", 0.9)],
            supported_language="en",
        )
        text = "Please review the file for [Cr-A2T5 HY23] and confirm."
        result = anonymizer.anonymize(text, "en", ad_hoc_recognizers=[force_person])
        assert result.anonymized_text == text
        assert result.entities == []

    def test_mixed_real_name_and_existing_placeholder(
        self, anonymizer: Anonymizer
    ) -> None:
        """Mixed input anonymizes only the real name; the existing placeholder stays put."""
        text = "John Smith reviewed the file submitted by [PERSON_1]."
        result = anonymizer.anonymize(text, "en")
        assert "submitted by [PERSON_1]" in result.anonymized_text
        assert "John Smith" not in result.anonymized_text
        person_entities = [e for e in result.entities if e.entity_type == "PERSON"]
        assert len(person_entities) == 1
        assert person_entities[0].original_text == "John Smith"

    def test_bare_text_matching_placeholder_shape_still_detected(
        self, anonymizer: Anonymizer
    ) -> None:
        """The guard only protects bracket-delimited spans, not bare look-alike text."""
        force_person = PatternRecognizer(
            supported_entity="PERSON",
            patterns=[Pattern("FORCE_PERSON", r"Cr-A2T5 HY23", 0.9)],
            supported_language="en",
        )
        text = "Please review the file for Cr-A2T5 HY23 and confirm."
        result = anonymizer.anonymize(text, "en", ad_hoc_recognizers=[force_person])
        assert "Cr-A2T5 HY23" not in result.anonymized_text
        assert any(e.entity_type == "PERSON" for e in result.entities)


# ---------------------------------------------------------------------------
# Per-language lazy loading (issue #62)
# ---------------------------------------------------------------------------


class TestAnonymizerLanguageLoading:
    def test_loads_only_requested_languages(self) -> None:
        instance = Anonymizer(languages=["en"])
        assert instance.loaded_languages == ["en"]

    def test_no_languages_starts_empty(self) -> None:
        instance = Anonymizer(languages=[])
        assert instance.loaded_languages == []

    def test_ensure_loaded_adds_language(self) -> None:
        instance = Anonymizer(languages=["en"])
        instance.ensure_loaded("nl")
        assert "nl" in instance.loaded_languages

    def test_ensure_loaded_is_idempotent(self) -> None:
        instance = Anonymizer(languages=["en"])
        instance.ensure_loaded("en")
        instance.ensure_loaded("en")
        assert instance.loaded_languages.count("en") == 1

    def test_anonymize_raises_for_unloaded_language(self) -> None:
        instance = Anonymizer(languages=["en"])
        with pytest.raises(ValueError):
            instance.anonymize("Jan de Vries woont in Amsterdam.", "nl")

    def test_anonymize_works_after_ensure_loaded(self) -> None:
        instance = Anonymizer(languages=["en"])
        instance.ensure_loaded("nl")
        result = instance.anonymize("Jan de Vries woont in Amsterdam.", "nl")
        assert isinstance(result, AnonymizationResult)


# ---------------------------------------------------------------------------
# LanguageDetector.ensure_loaded (issue #62)
# ---------------------------------------------------------------------------


class _StubRegistry:
    """Minimal stand-in for LanguageRegistry, tracking loaded state in memory."""

    def __init__(self, loaded: list[str] | None = None, raise_on_ensure: bool = False) -> None:
        self._loaded = set(loaded or [])
        self._raise_on_ensure = raise_on_ensure

    def is_loaded(self, language: str) -> bool:
        return language in self._loaded

    def ensure_loaded(self, language: str) -> None:
        if self._raise_on_ensure:
            raise RuntimeError("model not installed")
        self._loaded.add(language)


class TestLanguageDetectorEnsureLoaded:
    def test_no_registry_is_noop(self) -> None:
        detector = LanguageDetector()
        detector.ensure_loaded("nl", "eager")

    def test_eager_mode_passes_when_already_loaded(self) -> None:
        detector = LanguageDetector(registry=_StubRegistry(loaded=["en", "nl"]))
        detector.ensure_loaded("nl", "eager")

    def test_eager_mode_raises_when_not_loaded(self) -> None:
        detector = LanguageDetector(registry=_StubRegistry(loaded=["en"]))
        with pytest.raises(LanguageNotLoadedError):
            detector.ensure_loaded("nl", "eager")

    def test_lazy_mode_loads_on_demand(self) -> None:
        registry = _StubRegistry(loaded=["en"])
        detector = LanguageDetector(registry=registry)
        detector.ensure_loaded("nl", "lazy")
        assert registry.is_loaded("nl")

    def test_lazy_mode_raises_friendly_error_when_load_fails(self) -> None:
        registry = _StubRegistry(loaded=["en"], raise_on_ensure=True)
        detector = LanguageDetector(registry=registry)
        with pytest.raises(LanguageNotLoadedError):
            detector.ensure_loaded("nl", "lazy")

    def test_error_message_matches_required_wording(self) -> None:
        detector = LanguageDetector(registry=_StubRegistry(loaded=[]))
        with pytest.raises(LanguageNotLoadedError) as exc_info:
            detector.ensure_loaded("nl", "eager")
        assert str(exc_info.value) == (
            "Dutch detected but Dutch model is not enabled. "
            "Enable it in Settings > Languages and restart d-tach."
        )
