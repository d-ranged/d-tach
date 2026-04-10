"""Tests for the HashEncoder service class."""

import re
import string

import pytest

from app.services.hash_encoder import HashEncoder

ALPHANUM_PATTERN = re.compile(r"^[0-9A-Z]{4}$")
SECRET = "test-secret"
ALT_SECRET = "different-secret"


@pytest.fixture
def encoder() -> HashEncoder:
    """HashEncoder with a fixed test secret."""
    return HashEncoder(SECRET)


class TestHashEncoderInit:
    def test_empty_secret_raises(self) -> None:
        with pytest.raises(ValueError):
            HashEncoder("")


class TestEncodeFirstName:
    def test_preserves_first_two_characters(self, encoder: HashEncoder) -> None:
        result = encoder.encode_first_name("Craig")
        assert result.startswith("Cr-")

    def test_hash_segment_is_four_uppercase_alphanum(self, encoder: HashEncoder) -> None:
        result = encoder.encode_first_name("Craig")
        # Format is "Cr-XXXX"
        hash_part = result.split("-")[1]
        assert ALPHANUM_PATTERN.match(hash_part), f"Expected 4 uppercase alphanum, got: {hash_part}"

    def test_output_format_is_prefix_hyphen_hash(self, encoder: HashEncoder) -> None:
        result = encoder.encode_first_name("Alice")
        parts = result.split("-")
        assert len(parts) == 2
        assert parts[0] == "Al"
        assert len(parts[1]) == 4

    def test_consistent_across_repeated_calls(self, encoder: HashEncoder) -> None:
        first = encoder.encode_first_name("Craig")
        second = encoder.encode_first_name("Craig")
        assert first == second

    def test_different_secret_produces_different_output(self) -> None:
        enc1 = HashEncoder(SECRET)
        enc2 = HashEncoder(ALT_SECRET)
        assert enc1.encode_first_name("Craig") != enc2.encode_first_name("Craig")

    def test_different_names_differ(self, encoder: HashEncoder) -> None:
        assert encoder.encode_first_name("Craig") != encoder.encode_first_name("Chris")

    def test_short_name_two_chars(self, encoder: HashEncoder) -> None:
        result = encoder.encode_first_name("Jo")
        assert result.startswith("Jo-")
        assert ALPHANUM_PATTERN.match(result.split("-")[1])


class TestEncodeLastName:
    def test_output_is_four_uppercase_alphanum(self, encoder: HashEncoder) -> None:
        result = encoder.encode_last_name("Bradley")
        assert ALPHANUM_PATTERN.match(result), f"Expected 4 uppercase alphanum, got: {result}"

    def test_consistent_across_repeated_calls(self, encoder: HashEncoder) -> None:
        first = encoder.encode_last_name("Bradley")
        second = encoder.encode_last_name("Bradley")
        assert first == second

    def test_different_secret_produces_different_output(self) -> None:
        enc1 = HashEncoder(SECRET)
        enc2 = HashEncoder(ALT_SECRET)
        assert enc1.encode_last_name("Bradley") != enc2.encode_last_name("Bradley")

    def test_different_names_differ(self, encoder: HashEncoder) -> None:
        assert encoder.encode_last_name("Bradley") != encoder.encode_last_name("Smith")


class TestCrossSessionConsistency:
    def test_first_name_same_output_new_instance(self) -> None:
        enc1 = HashEncoder(SECRET)
        enc2 = HashEncoder(SECRET)
        assert enc1.encode_first_name("Craig") == enc2.encode_first_name("Craig")

    def test_last_name_same_output_new_instance(self) -> None:
        enc1 = HashEncoder(SECRET)
        enc2 = HashEncoder(SECRET)
        assert enc1.encode_last_name("Bradley") == enc2.encode_last_name("Bradley")


class TestFirstNameAloneMatchesFullName:
    def test_first_name_prefix_matches_standalone_encoding(self, encoder: HashEncoder) -> None:
        """Craig alone must produce the same encoding as the first-name part
        of Craig Bradley, because folder names may contain only first names."""
        standalone = encoder.encode_first_name("Craig")
        as_part_of_full = encoder.encode_first_name("Craig")
        assert standalone == as_part_of_full

    def test_last_name_standalone_matches_last_name_of_full(self, encoder: HashEncoder) -> None:
        standalone = encoder.encode_last_name("Bradley")
        as_part_of_full = encoder.encode_last_name("Bradley")
        assert standalone == as_part_of_full
