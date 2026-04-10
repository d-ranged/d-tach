"""Tests for LanguageDetector and Anonymizer service classes."""

import pytest

from app.services.anonymizer import Anonymizer, AnonymizationResult, DutchBsnRecognizer
from app.services.language_detector import LanguageDetector


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
        assert "EMAIL_ADDRESS_1" in email_placeholders
        if len(email_placeholders) > 1:
            assert "EMAIL_ADDRESS_2" in email_placeholders

    def test_result_type_is_correct(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize("Hello world.", "en")
        assert isinstance(result, AnonymizationResult)
        assert isinstance(result.anonymized_text, str)
        assert isinstance(result.entities, list)
