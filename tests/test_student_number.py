"""Tests for student number detection: PatternConfig, StudentNumberRecognizer, Anonymizer."""

import re

import pytest

from app.services.anonymizer import (
    Anonymizer,
    ENTITIES,
    STUDENT_NUMBER_ENTITY,
    StudentNumberRecognizer,
    build_student_number_recognizer,
)
from app.services.pattern_config import PatternConfig


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def anonymizer() -> Anonymizer:
    """Single Anonymizer instance shared across tests (spaCy models load once)."""
    return Anonymizer()


def _en_entities_no_dates() -> list[str]:
    """Entity list without DATE_TIME, to avoid spurious matches in unit tests."""
    return [e for e in ENTITIES if e != "DATE_TIME"]


# ---------------------------------------------------------------------------
# PatternConfig.student_number_enabled
# ---------------------------------------------------------------------------


class TestPatternConfigStudentNumber:
    def test_default_is_disabled(self) -> None:
        config = PatternConfig()
        assert config.student_number_enabled is False

    def test_can_be_enabled(self) -> None:
        config = PatternConfig(student_number_enabled=True)
        assert config.student_number_enabled is True

    def test_round_trips_through_dict_disabled(self) -> None:
        config = PatternConfig(student_number_enabled=False)
        assert PatternConfig.from_dict(config.to_dict()).student_number_enabled is False

    def test_round_trips_through_dict_enabled(self) -> None:
        config = PatternConfig(student_number_enabled=True)
        assert PatternConfig.from_dict(config.to_dict()).student_number_enabled is True

    def test_from_dict_missing_key_defaults_to_false(self) -> None:
        config = PatternConfig.from_dict({"digit_count": 7})
        assert config.student_number_enabled is False


# ---------------------------------------------------------------------------
# StudentNumberRecognizer — regex correctness via the Anonymizer
# (PatternRecognizer.analyze() requires the full NLP pipeline context;
#  testing through Anonymizer.anonymize() with ad_hoc_recognizers is the
#  correct integration point.)
# ---------------------------------------------------------------------------


class TestStudentNumberRecognizer:
    def _recognizer(self, digit_count: int = 7) -> StudentNumberRecognizer:
        return build_student_number_recognizer(PatternConfig(digit_count=digit_count), "en")

    def test_matches_exact_digit_count(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Student ID: 1234567 enrolled.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "1234567" not in result.anonymized_text
        assert STUDENT_NUMBER_ENTITY in result.anonymized_text

    def test_does_not_match_wrong_digit_count(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Reference 123456 here.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "123456" in result.anonymized_text

    def test_does_not_match_longer_digit_string(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Value 123456789 noted.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "123456789" in result.anonymized_text

    def test_currency_prefix_excluded(self, anonymizer: Anonymizer) -> None:
        for symbol in ("€", "$", "£"):
            result = anonymizer.anonymize(
                f"Amount {symbol}1234567.",
                language="en",
                entities=[STUDENT_NUMBER_ENTITY],
                ad_hoc_recognizers=[self._recognizer(7)],
            )
            assert "1234567" in result.anonymized_text, (
                f"Should not match after currency symbol {symbol!r}"
            )

    def test_matches_at_start_of_string(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "1234567 is the student ID.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "1234567" not in result.anonymized_text

    def test_matches_at_end_of_string(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Student ID is 1234567",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "1234567" not in result.anonymized_text

    def test_respects_configured_digit_count(self, anonymizer: Anonymizer) -> None:
        for n in (4, 6, 8, 10):
            number = "1" * n
            result = anonymizer.anonymize(
                f"ID {number} here.",
                language="en",
                entities=[STUDENT_NUMBER_ENTITY],
                ad_hoc_recognizers=[self._recognizer(n)],
            )
            assert number not in result.anonymized_text, f"Should match {n}-digit number"

    def test_build_helper_returns_recognizer(self) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_student_number_recognizer(config, "en")
        assert isinstance(recognizer, StudentNumberRecognizer)


# ---------------------------------------------------------------------------
# Anonymizer with ad-hoc StudentNumberRecognizer
# ---------------------------------------------------------------------------


class TestAnonymizerStudentNumber:
    def test_student_number_replaced_when_enabled(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_student_number_recognizer(config, "en")

        result = anonymizer.anonymize(
            "Student 1234567 submitted the report.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert "1234567" not in result.anonymized_text
        assert "STUDENT_NUMBER_1" in result.anonymized_text

    def test_student_number_not_replaced_without_recognizer(self, anonymizer: Anonymizer) -> None:
        # Without the ad-hoc recognizer, 7-digit sequences are not flagged as
        # student numbers. Exclude DATE_TIME to avoid spurious date matches.
        result = anonymizer.anonymize(
            "Student 1234567 submitted the report.",
            language="en",
            entities=_en_entities_no_dates(),
        )
        assert "1234567" in result.anonymized_text

    def test_same_number_gets_same_placeholder(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_student_number_recognizer(config, "en")

        result = anonymizer.anonymize(
            "ID 1234567 and again 1234567.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert result.anonymized_text.count("STUDENT_NUMBER_1") == 2

    def test_two_different_numbers_get_different_placeholders(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_student_number_recognizer(config, "en")

        result = anonymizer.anonymize(
            "First 1234567 and second 7654321.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        placeholders = {e.placeholder for e in result.entities}
        assert len(placeholders) == 2

    def test_currency_amount_not_replaced(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_student_number_recognizer(config, "en")

        result = anonymizer.anonymize(
            "Paid €1234567 for the course.",
            language="en",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert "1234567" in result.anonymized_text

    def test_works_with_other_entities_simultaneously(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_student_number_recognizer(config, "en")
        entities = _en_entities_no_dates() + [STUDENT_NUMBER_ENTITY]

        result = anonymizer.anonymize(
            "Alice submitted report for student number 1234567.",
            language="en",
            entities=entities,
            ad_hoc_recognizers=[recognizer],
        )

        assert "Alice" not in result.anonymized_text
        assert "1234567" not in result.anonymized_text

    def test_dutch_student_number_detected(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_student_number_recognizer(config, "nl")

        result = anonymizer.anonymize(
            "Studentnummer 1234567 ingediend.",
            language="nl",
            entities=[STUDENT_NUMBER_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert "1234567" not in result.anonymized_text
