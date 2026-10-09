"""Tests for the lone-name matching rules shared by class list import and detection (issue #76)."""

import re

import pytest

from app.services import name_rules
from app.services.name_rules import (
    RULE_ANY,
    RULE_CAPITAL,
    RULE_SHORT,
    classify_name,
    lone_name_pattern,
    ordinary_words,
)


class TestClassifyName:
    @pytest.mark.parametrize("name", ["An", "an", "En", "El", "Jo"])
    def test_two_letters_or_fewer_is_short(self, name: str) -> None:
        assert classify_name(name) == RULE_SHORT

    @pytest.mark.parametrize("name", ["Will", "Mark", "Bos", "Visser", "Ben"])
    def test_ordinary_word_is_capital(self, name: str) -> None:
        assert classify_name(name) == RULE_CAPITAL

    @pytest.mark.parametrize("name", ["Lotte", "Vermeulen", "Jansen"])
    def test_other_name_is_any(self, name: str) -> None:
        assert classify_name(name) == RULE_ANY

    @pytest.mark.parametrize("name", ["van Dijk", "de Boer", "An Jansen", "Will Visser"])
    def test_more_than_one_word_is_any(self, name: str) -> None:
        assert classify_name(name) == RULE_ANY

    @pytest.mark.parametrize("name", ["Koen", "Kees", "Eva", "Thomas"])
    def test_excluded_names_are_any(self, name: str) -> None:
        assert classify_name(name) == RULE_ANY


class TestWordList:
    def test_both_languages_are_in_one_set(self) -> None:
        words = ordinary_words()
        assert "will" in words
        assert "visser" in words

    def test_loaded_once(self) -> None:
        assert ordinary_words() is ordinary_words()

    def test_words_are_lowercase_and_three_to_twelve_letters(self) -> None:
        words = ordinary_words()
        assert not any(word.startswith("#") for word in words)
        assert all(word == word.lower() for word in words)
        assert all(3 <= len(word) <= 12 for word in words)

    def test_list_files_ship_with_their_licences(self) -> None:
        for file_name in name_rules.WORD_LIST_FILES:
            assert (name_rules.WORD_LIST_DIR / file_name).is_file()
        assert (name_rules.WORD_LIST_DIR / "LICENSE-ordinary-words-en.txt").is_file()
        assert (name_rules.WORD_LIST_DIR / "LICENSE-ordinary-words-nl.txt").is_file()


class TestLoneNamePattern:
    @staticmethod
    def _find(body: str, text: str) -> list[str]:
        # Presidio compiles with ignore-case on, so the tests do the same.
        flags = re.DOTALL | re.MULTILINE | re.IGNORECASE
        return re.findall(rf"(?<!\w)(?:{body})(?!\w)", text, flags)

    def test_short_has_no_pattern(self) -> None:
        assert lone_name_pattern("An", RULE_SHORT) is None

    def test_capital_matches_capital_and_all_caps_not_lowercase(self) -> None:
        body = lone_name_pattern("Will", RULE_CAPITAL)
        assert self._find(body, "Will did well, we will see. WILL too.") == ["Will", "WILL"]

    def test_capital_does_not_match_inside_longer_words(self) -> None:
        body = lone_name_pattern("Will", RULE_CAPITAL)
        assert self._find(body, "Willem and Goodwill") == []

    def test_capital_rule_capitalises_a_lowercase_stored_value(self) -> None:
        body = lone_name_pattern("will", RULE_CAPITAL)
        assert self._find(body, "Will did well, we will see.") == ["Will"]

    def test_any_matches_however_written(self) -> None:
        body = lone_name_pattern("Lotte", RULE_ANY)
        assert self._find(body, "Lotte and lotte and LOTTE") == ["Lotte", "lotte", "LOTTE"]

    def test_special_characters_are_escaped(self) -> None:
        body = lone_name_pattern("O'Brien (jr)", RULE_ANY)
        assert self._find(body, "O'Brien (jr) came") == ["O'Brien (jr)"]
