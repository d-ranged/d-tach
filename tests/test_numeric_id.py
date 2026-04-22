"""Tests for numeric ID detection: PatternConfig, NumericIdRecognizer, Anonymizer."""

import pytest

from app.services.anonymizer import (
    Anonymizer,
    ENTITIES,
    NUMERIC_ID_ENTITY,
    NumericIdRecognizer,
    build_numeric_id_recognizer,
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
# PatternConfig.numeric_id_enabled
# ---------------------------------------------------------------------------


class TestPatternConfigNumericId:
    def test_default_is_disabled(self) -> None:
        config = PatternConfig()
        assert config.numeric_id_enabled is False

    def test_can_be_enabled(self) -> None:
        config = PatternConfig(numeric_id_enabled=True)
        assert config.numeric_id_enabled is True

    def test_round_trips_through_dict_disabled(self) -> None:
        config = PatternConfig(numeric_id_enabled=False)
        assert PatternConfig.from_dict(config.to_dict()).numeric_id_enabled is False

    def test_round_trips_through_dict_enabled(self) -> None:
        config = PatternConfig(numeric_id_enabled=True)
        assert PatternConfig.from_dict(config.to_dict()).numeric_id_enabled is True

    def test_from_dict_missing_key_defaults_to_false(self) -> None:
        config = PatternConfig.from_dict({"digit_count": 7})
        assert config.numeric_id_enabled is False

    def test_migrates_old_student_number_enabled_key(self) -> None:
        # Settings files written by the previous version use student_number_enabled
        config = PatternConfig.from_dict({"digit_count": 7, "student_number_enabled": True})
        assert config.numeric_id_enabled is True


# ---------------------------------------------------------------------------
# NumericIdRecognizer — tested via Anonymizer.anonymize() with ad_hoc_recognizers
# (PatternRecognizer.analyze() requires the full NLP pipeline context.)
# ---------------------------------------------------------------------------


class TestNumericIdRecognizer:
    def _recognizer(self, digit_count: int = 7) -> NumericIdRecognizer:
        return build_numeric_id_recognizer(PatternConfig(digit_count=digit_count), "en")

    def test_matches_exact_digit_count(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Student ID: 1234567 enrolled.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "1234567" not in result.anonymized_text
        assert NUMERIC_ID_ENTITY in result.anonymized_text

    def test_does_not_match_wrong_digit_count(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Reference 123456 here.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "123456" in result.anonymized_text

    def test_does_not_match_longer_digit_string(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Value 123456789 noted.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "123456789" in result.anonymized_text

    def test_currency_prefix_excluded(self, anonymizer: Anonymizer) -> None:
        for symbol in ("€", "$", "£"):
            result = anonymizer.anonymize(
                f"Amount {symbol}1234567.",
                language="en",
                entities=[NUMERIC_ID_ENTITY],
                ad_hoc_recognizers=[self._recognizer(7)],
            )
            assert "1234567" in result.anonymized_text, (
                f"Should not match after currency symbol {symbol!r}"
            )

    def test_matches_at_start_of_string(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "1234567 is the student ID.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "1234567" not in result.anonymized_text

    def test_matches_at_end_of_string(self, anonymizer: Anonymizer) -> None:
        result = anonymizer.anonymize(
            "Student ID is 1234567",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[self._recognizer(7)],
        )
        assert "1234567" not in result.anonymized_text

    def test_respects_configured_digit_count(self, anonymizer: Anonymizer) -> None:
        for n in (4, 6, 8, 10):
            number = "1" * n
            result = anonymizer.anonymize(
                f"ID {number} here.",
                language="en",
                entities=[NUMERIC_ID_ENTITY],
                ad_hoc_recognizers=[self._recognizer(n)],
            )
            assert number not in result.anonymized_text, f"Should match {n}-digit number"

    def test_build_helper_returns_recognizer(self) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_numeric_id_recognizer(config, "en")
        assert isinstance(recognizer, NumericIdRecognizer)


# ---------------------------------------------------------------------------
# Anonymizer with ad-hoc NumericIdRecognizer
# ---------------------------------------------------------------------------


class TestAnonymizerNumericId:
    def test_numeric_id_replaced_when_enabled(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_numeric_id_recognizer(config, "en")

        result = anonymizer.anonymize(
            "Student 1234567 submitted the report.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert "1234567" not in result.anonymized_text
        assert "[NUMERIC_ID_1]" in result.anonymized_text

    def test_numeric_id_not_replaced_without_recognizer(self, anonymizer: Anonymizer) -> None:
        # Without the ad-hoc recognizer, 7-digit sequences are not flagged.
        # Exclude DATE_TIME to avoid spurious date matches.
        result = anonymizer.anonymize(
            "Student 1234567 submitted the report.",
            language="en",
            entities=_en_entities_no_dates(),
        )
        assert "1234567" in result.anonymized_text

    def test_same_number_gets_same_placeholder(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_numeric_id_recognizer(config, "en")

        result = anonymizer.anonymize(
            "ID 1234567 and again 1234567.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert result.anonymized_text.count("[NUMERIC_ID_1]") == 2

    def test_two_different_numbers_get_different_placeholders(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_numeric_id_recognizer(config, "en")

        result = anonymizer.anonymize(
            "First 1234567 and second 7654321.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        placeholders = {e.placeholder for e in result.entities}
        assert len(placeholders) == 2

    def test_currency_amount_not_replaced(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_numeric_id_recognizer(config, "en")

        result = anonymizer.anonymize(
            "Paid €1234567 for the course.",
            language="en",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert "1234567" in result.anonymized_text

    def test_works_with_other_entities_simultaneously(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_numeric_id_recognizer(config, "en")
        entities = _en_entities_no_dates() + [NUMERIC_ID_ENTITY]

        result = anonymizer.anonymize(
            "Alice submitted report for ID 1234567.",
            language="en",
            entities=entities,
            ad_hoc_recognizers=[recognizer],
        )

        assert "Alice" not in result.anonymized_text
        assert "1234567" not in result.anonymized_text

    def test_dutch_numeric_id_detected(self, anonymizer: Anonymizer) -> None:
        config = PatternConfig(digit_count=7)
        recognizer = build_numeric_id_recognizer(config, "nl")

        result = anonymizer.anonymize(
            "Studentnummer 1234567 ingediend.",
            language="nl",
            entities=[NUMERIC_ID_ENTITY],
            ad_hoc_recognizers=[recognizer],
        )

        assert "1234567" not in result.anonymized_text
