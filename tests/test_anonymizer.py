"""Tests for LanguageDetector and Anonymizer service classes."""

import re
import pytest

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

from app.services.anonymizer import (
    Anonymizer,
    AnonymizationResult,
    DutchBsnRecognizer,
    ENTITIES,
    URL_ENTITY,
    build_known_value_recognizers,
)
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
    def test_partial_span_inside_a_placeholder_is_not_wrapped_again(
        self, anonymizer: Anonymizer
    ) -> None:
        """NER tagging 'Lo-NUSA 0W3X' without its brackets must not re-wrap it (#72)."""
        for text in (
            "progress [Lo-NUSA 0W3X]",
            "progress [Lo-NUSA_0W3X]",
            "progress [Lo-NUSA 0W3X] reference",
        ):
            assert anonymizer.anonymize(text, "en").anonymized_text == text

    def test_span_overlapping_a_placeholder_is_dropped(self, anonymizer: Anonymizer) -> None:
        from app.services.anonymizer import _overlaps_placeholder

        spans = [(9, 24)]
        assert _overlaps_placeholder(spans, 10, 22)
        assert _overlaps_placeholder(spans, 0, 12)
        assert not _overlaps_placeholder(spans, 0, 9)
        assert not _overlaps_placeholder(spans, 24, 30)

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
# build_known_value_recognizers (issue #66 — class list import)
# ---------------------------------------------------------------------------


class TestBuildKnownValueRecognizers:
    def test_defaults_to_person_entity(self) -> None:
        recognizers = build_known_value_recognizers(
            [{"value": "Craig Bradley"}], "en"
        )
        assert len(recognizers) == 1
        assert recognizers[0].supported_entities == ["PERSON"]

    def test_uses_entrys_own_entity_type(self) -> None:
        recognizers = build_known_value_recognizers(
            [{"value": "123456", "entity_type": "NUMERIC_ID", "source": "class_list"}], "en"
        )
        assert recognizers[0].supported_entities == ["NUMERIC_ID"]

    def test_blank_value_is_skipped(self) -> None:
        recognizers = build_known_value_recognizers(
            [{"value": "   "}, {"value": "Real Name"}], "en"
        )
        assert len(recognizers) == 1

    def test_mixed_entity_types_produce_independent_recognizers(self) -> None:
        recognizers = build_known_value_recognizers(
            [
                {"value": "Craig Bradley", "entity_type": "PERSON"},
                {"value": "123456", "entity_type": "NUMERIC_ID"},
                {"value": "craig@example.com", "entity_type": "EMAIL_ADDRESS"},
            ],
            "en",
        )
        types = {r.supported_entities[0] for r in recognizers}
        assert types == {"PERSON", "NUMERIC_ID", "EMAIL_ADDRESS"}

    def test_numeric_id_known_value_detected_even_without_toggle(
        self, anonymizer: Anonymizer
    ) -> None:
        """A class-list NUMERIC_ID known value must anonymize as NUMERIC_ID_N.

        This must work even though the caller passes only NUMERIC_ID in the
        entities list explicitly here — file_processor._build_entity_list is
        responsible for unioning it in automatically outside of this test.
        """
        recognizers = build_known_value_recognizers(
            [{"value": "998877", "entity_type": "NUMERIC_ID", "source": "class_list"}], "en"
        )
        text = "Student number 998877 was submitted late."
        result = anonymizer.anonymize(
            text, "en", entities=ENTITIES + ["NUMERIC_ID"], ad_hoc_recognizers=recognizers
        )
        assert "[NUMERIC_ID_1]" in result.anonymized_text
        assert "998877" not in result.anonymized_text


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


class TestKnownValuesMatchWholeWordsOnly:
    """A known value must never match inside a longer word.

    Regression guard: a class list containing the name "An" turned "Thank you"
    into "Th[PERSON_1]k you" and "standard" into "st[PERSON_1]dard", corrupting
    ordinary prose throughout every document processed.
    """

    def test_short_known_value_does_not_match_inside_words(self) -> None:
        from app.services.anonymizer import build_known_value_recognizers

        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [{"value": "An", "entity_type": "PERSON"}], "en"
        )

        result = anonymizer.anonymize(
            "Thank you for the plan and the standard forms.",
            language="en",
            ad_hoc_recognizers=recognizers,
        )

        assert result.anonymized_text == "Thank you for the plan and the standard forms."

    def test_the_same_value_is_still_caught_as_a_standalone_word(self) -> None:
        from app.services.anonymizer import build_known_value_recognizers

        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [{"value": "An", "entity_type": "PERSON"}], "en"
        )

        result = anonymizer.anonymize(
            "An attended the meeting.", language="en", ad_hoc_recognizers=recognizers
        )

        assert "[PERSON_1]" in result.anonymized_text
        assert "An attended" not in result.anonymized_text

    def test_multi_word_known_value_still_matches(self) -> None:
        from app.services.anonymizer import build_known_value_recognizers

        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [{"value": "An Nguyen", "entity_type": "PERSON"}], "en"
        )

        result = anonymizer.anonymize(
            "An Nguyen submitted the form.", language="en", ad_hoc_recognizers=recognizers
        )

        assert "[PERSON_1]" in result.anonymized_text
        assert "Nguyen" not in result.anonymized_text

    def test_punctuation_adjacent_known_value_still_matches(self) -> None:
        from app.services.anonymizer import build_known_value_recognizers

        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [{"value": "Din", "entity_type": "PERSON"}], "en"
        )

        result = anonymizer.anonymize(
            "Dear Din, please sign. (Din agreed.)",
            language="en",
            ad_hoc_recognizers=recognizers,
        )

        assert "Din" not in result.anonymized_text


class TestKnownValuesAreGroupedPerEntityType:
    """A large class list must not become one recognizer per value.

    A roster of 500 students with a name column and a number column produces
    over a thousand known values. One recognizer each means Presidio makes a
    thousand separate passes over every document processed.
    """

    def test_many_values_of_one_type_share_a_single_recognizer(self) -> None:
        values = [{"value": f"Student {n}", "entity_type": "PERSON"} for n in range(500)]

        recognizers = build_known_value_recognizers(values, "en")

        assert len(recognizers) == 1

    def test_values_differing_only_in_case_are_deduplicated(self) -> None:
        recognizers = build_known_value_recognizers(
            [
                {"value": "Craig Bradley", "entity_type": "PERSON"},
                {"value": "craig bradley", "entity_type": "PERSON"},
            ],
            "en",
        )

        assert len(recognizers) == 1
        assert recognizers[0].patterns[0].regex.count("|") == 0

    def test_longer_value_wins_over_a_shorter_one_that_prefixes_it(self) -> None:
        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [
                {"value": "An", "entity_type": "PERSON"},
                {"value": "An Nguyen", "entity_type": "PERSON"},
            ],
            "en",
        )

        result = anonymizer.anonymize(
            "An Nguyen submitted the form.", language="en", ad_hoc_recognizers=recognizers
        )

        assert "Nguyen" not in result.anonymized_text

    def test_each_entity_type_still_gets_its_own_recognizer(self) -> None:
        recognizers = build_known_value_recognizers(
            [
                {"value": "Craig Bradley", "entity_type": "PERSON"},
                {"value": "Ann Other", "entity_type": "PERSON"},
                {"value": "123456", "entity_type": "NUMERIC_ID"},
            ],
            "en",
        )

        assert len(recognizers) == 2
        assert {r.supported_entities[0] for r in recognizers} == {"PERSON", "NUMERIC_ID"}


class TestOverlappingDetectionsDoNotCorruptOutput:
    """Overlapping spans must produce one placeholder, not two interleaved ones.

    Regression guard: with a surname-only known values list, NER reports the
    full name and the known value reports the surname inside it. Both spans
    were replaced, so "Din Bakker submitted" came out as "[PERSON_1]N_2]
    submitted" — output no restore pass can map back.
    """

    def test_known_value_inside_an_ner_span_produces_one_placeholder(self) -> None:
        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [{"value": "Bakker", "entity_type": "PERSON"}], "en"
        )

        result = anonymizer.anonymize(
            "Din Bakker submitted the report late.",
            language="en",
            ad_hoc_recognizers=recognizers,
        )

        assert result.anonymized_text == "[PERSON_1] submitted the report late."

    def test_no_malformed_placeholder_survives_in_the_output(self) -> None:
        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [{"value": "Bakker", "entity_type": "PERSON"}], "en"
        )

        result = anonymizer.anonymize(
            "I spoke to Bakker about it, and Din Bakker agreed.",
            language="en",
            ad_hoc_recognizers=recognizers,
        )

        # Every "]" must close a "[" that opened a well-formed placeholder.
        assert re.fullmatch(
            r"[^\[\]]*(?:\[[A-Z_]+_\d+\][^\[\]]*)*", result.anonymized_text
        ), result.anonymized_text
        assert "Bakker" not in result.anonymized_text

    def test_the_wider_span_wins_over_the_higher_scoring_narrow_one(self) -> None:
        """A known value scores 0.99 and NER ~0.85, so score alone would shrink
        the span down to the surname and leave the first name in the clear."""
        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(
            [{"value": "Bakker", "entity_type": "PERSON"}], "en"
        )

        result = anonymizer.anonymize(
            "Din Bakker submitted the report late.",
            language="en",
            ad_hoc_recognizers=recognizers,
        )

        assert "Din" not in result.anonymized_text


class TestPossessiveFormsHashTheSame:
    """The same person must produce the same value however the name is written.

    spaCy includes the possessive in the PERSON span, so "Vandenberg's" used to
    be hashed as a different string from "Vandenberg" — and differently again
    for the typographic apostrophe Word autocorrects to. Three tokens, one
    person, and no way for a reader of the anonymized folder to tell.
    """

    def _value(self, anonymizer: Anonymizer, text: str) -> str:
        result = anonymizer.anonymize(text, language="en")
        people = [e.original_text for e in result.entities if e.entity_type == "PERSON"]
        assert people, f"no PERSON detected in {text!r}"
        return people[0]

    def test_straight_apostrophe_matches_the_bare_name(self, anonymizer) -> None:
        bare = self._value(anonymizer, "Marcus Vandenberg submitted the report late.")

        assert self._value(anonymizer, "Marcus Vandenberg's report was late.") == bare

    def test_typographic_apostrophe_matches_the_bare_name(self, anonymizer) -> None:
        bare = self._value(anonymizer, "Marcus Vandenberg submitted the report late.")

        assert self._value(anonymizer, "Marcus Vandenberg’s report was late.") == bare

    def test_apostrophe_stays_in_the_output_text(self, anonymizer) -> None:
        """Trimming the span must not eat the punctuation the sentence needs."""
        result = anonymizer.anonymize("Marcus Vandenberg's report was late.", language="en")

        assert "'s report was late." in result.anonymized_text
        assert "Vandenberg" not in result.anonymized_text

    def test_plural_possessive_keeps_the_s(self, anonymizer) -> None:
        """"Vandenbergs'" is a different surname form, so only the quote comes off."""
        result = anonymizer.anonymize("The Vandenbergs' address is on file.", language="en")
        people = [e.original_text for e in result.entities if e.entity_type == "PERSON"]

        assert people == ["Vandenbergs"]
        assert "' address is on file." in result.anonymized_text

    def test_a_span_that_is_only_an_apostrophe_is_left_alone(self) -> None:
        """Guard against trimming a span down to nothing and inverting start/end."""
        span = RecognizerResult(entity_type="PERSON", start=0, end=1, score=0.85)

        trimmed = Anonymizer._trim_possessive([span], "'")

        assert (trimmed[0].start, trimmed[0].end) == (0, 1)


class TestNameSpansStopAtLineBreaks:
    """A name at a line end must not swallow the line break or the next word (#74)."""

    def test_signature_keeps_the_line_break_and_next_word(self, anonymizer) -> None:
        text = "Regards,\nJoris van Dijk\nGuide for the internship"

        result = anonymizer.anonymize(text, language="en")

        assert result.anonymized_text == "Regards,\n[PERSON_1]\nGuide for the internship"
        assert [e.original_text for e in result.entities] == ["Joris van Dijk"]

    def test_mid_sentence_name_before_a_new_line(self, anonymizer) -> None:
        text = "Signed by Joris van Dijk\nGuide for the internship"

        result = anonymizer.anonymize(text, language="en")

        assert "\nGuide for the internship" in result.anonymized_text
        assert "Dijk" not in result.anonymized_text

    def test_windows_line_endings_are_kept(self, anonymizer) -> None:
        result = anonymizer.anonymize("Regards,\r\nJoris van Dijk\r\nGuide", language="en")

        assert result.anonymized_text.endswith("\r\nGuide")

    def test_span_that_is_only_a_line_break_is_dropped(self) -> None:
        span = RecognizerResult(entity_type="PERSON", start=0, end=3, score=0.85)

        assert Anonymizer._trim_at_line_break([span], "\nGuide") == []

    def test_location_span_is_cut_too(self) -> None:
        span = RecognizerResult(entity_type="LOCATION", start=0, end=21, score=0.85)

        trimmed = Anonymizer._trim_at_line_break([span], "Amsterdam\nNetherlands x")

        assert (trimmed[0].start, trimmed[0].end) == (0, 9)

    def test_other_entity_types_are_not_cut(self) -> None:
        span = RecognizerResult(entity_type="DATE_TIME", start=0, end=10, score=0.85)

        trimmed = Anonymizer._trim_at_line_break([span], "1 May\n2026 x")

        assert (trimmed[0].start, trimmed[0].end) == (0, 10)


class TestKnownValueRules:
    """Issue #76: a lone first name or surname is matched by its stored rule."""

    @staticmethod
    def _anonymize(entries: list[dict], text: str) -> str:
        anonymizer = Anonymizer(languages=["en"])
        recognizers = build_known_value_recognizers(entries, "en")
        return anonymizer.anonymize(
            text, language="en", ad_hoc_recognizers=recognizers
        ).anonymized_text

    @staticmethod
    def _entry(value: str, rule: str, part: str) -> dict:
        return {
            "value": value, "entity_type": "PERSON", "source": "class_list",
            "rule": rule, "name_part": part,
        }

    def test_short_entry_is_skipped(self) -> None:
        recognizers = build_known_value_recognizers([self._entry("An", "short", "first")], "en")
        assert recognizers == []

    def test_an_jansen_full_name_replaced_and_plain_words_stay(self) -> None:
        entries = [
            self._entry("An Jansen", "any", "full"),
            self._entry("An", "short", "first"),
            self._entry("Jansen", "any", "surname"),
        ]
        assert "An Jansen" not in self._anonymize(entries, "An Jansen wrote it.")
        for text in ("Thank you, an excellent report.", "An handed it in."):
            assert self._anonymize(entries, text) == text

    def test_will_visser_capital_rule(self) -> None:
        entries = [
            self._entry("Will Visser", "any", "full"),
            self._entry("Will", "capital", "first"),
            self._entry("Visser", "capital", "surname"),
        ]
        assert "Will" not in self._anonymize(entries, "Will did well.")
        assert self._anonymize(entries, "We will see.") == "We will see."

    def test_lotte_vermeulen_matches_any_case(self) -> None:
        entries = [
            self._entry("Lotte Vermeulen", "any", "full"),
            self._entry("Lotte", "any", "first"),
            self._entry("Vermeulen", "any", "surname"),
        ]
        assert "Lotte" not in self._anonymize(entries, "Lotte was there.")
        assert "lotte" not in self._anonymize(entries, "I asked lotte about it.")


class TestLoneFirstNameAfterFullName:
    """Issue #75: a lone first name is replaced when its full name is, same text only."""

    @staticmethod
    def _entry(value: str) -> dict:
        return {"value": value, "entity_type": "PERSON", "source": "class_list", "rule": "any"}

    def _run(self, anonymizer, full_name: str, text: str) -> AnonymizationResult:
        recognizers = build_known_value_recognizers([self._entry(full_name)], "en")
        return anonymizer.anonymize(text, language="en", ad_hoc_recognizers=recognizers)

    @staticmethod
    def _find(text: str, full_name: str, **kwargs) -> list:
        start = text.index(full_name)
        full = RecognizerResult("PERSON", start, start + len(full_name), 0.85)
        return Anonymizer._lone_first_names([full], text, kwargs.get("placeholders", []))

    def test_lone_first_name_after_full_name_is_replaced(self, anonymizer) -> None:
        text = "Progress report for Lotte Vermeulen.\nMidterm visit, week 10. Lotte is on track."

        result = self._run(anonymizer, "Lotte Vermeulen", text)

        assert "Lotte" not in result.anonymized_text
        assert result.anonymized_text.endswith("[PERSON_2] is on track.")

    def test_works_from_a_ner_result_with_no_known_values(self) -> None:
        text = "Report for Lotte Vermeulen. Later, Lotte is on track."

        found = self._find(text, "Lotte Vermeulen")

        assert [text[r.start:r.end] for r in found] == ["Lotte"]

    def test_lowercase_first_name_is_replaced(self) -> None:
        text = "Report for Lotte Vermeulen. I asked lotte about it."

        found = self._find(text, "Lotte Vermeulen")

        assert [text[r.start:r.end] for r in found] == ["lotte"]

    def test_short_first_name_is_never_matched_alone(self, anonymizer) -> None:
        text = "An Jansen handed in. Thank you, an excellent report. An handed it in."

        result = self._run(anonymizer, "An Jansen", text)

        assert "an excellent report" in result.anonymized_text
        assert "An handed it in" in result.anonymized_text
        assert "Jansen" not in result.anonymized_text

    def test_ordinary_word_first_name_needs_a_capital(self, anonymizer) -> None:
        text = "Will Visser presented. We will see. Will did well."

        result = self._run(anonymizer, "Will Visser", text)

        assert "We will see" in result.anonymized_text
        assert "Will did well" not in result.anonymized_text
        assert result.anonymized_text.count("[PERSON_") == 2

    def test_not_carried_across_documents(self, anonymizer) -> None:
        first = self._run(anonymizer, "Lotte Vermeulen", "Report for Lotte Vermeulen, then lotte left.")
        second = anonymizer.anonymize("Then lotte left.", language="en")

        assert "lotte" not in first.anonymized_text
        assert second.anonymized_text == "Then lotte left."

    def test_full_name_twice_keeps_the_full_name_placeholder(self, anonymizer) -> None:
        text = "Lotte Vermeulen wrote it. Lotte Vermeulen signed it."

        result = self._run(anonymizer, "Lotte Vermeulen", text)

        assert result.anonymized_text == "[PERSON_1] wrote it. [PERSON_1] signed it."

    def test_match_inside_an_existing_placeholder_is_dropped(self) -> None:
        text = "Report for Lotte Vermeulen. See [Lo-NUSA] here."
        placeholder = [(text.index("[Lo"), text.index("] here") + 1)]

        assert self._find(text, "Lotte Vermeulen", placeholders=placeholder) == []

    def test_single_word_person_gives_no_first_name(self) -> None:
        text = "Lotte met Lotte."
        single = RecognizerResult("PERSON", 0, 5, 0.85)

        assert Anonymizer._lone_first_names([single], text, []) == []

    def test_hashed_lone_first_name_uses_the_first_name_form(self) -> None:
        from app.services.hash_encoder import HashEncoder

        encoded = HashEncoder("test-secret").encode_full_name("Lotte")

        assert re.fullmatch(r"Lo-[A-Z0-9]{4}", encoded)
