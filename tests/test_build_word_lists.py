"""Tests for tools/build_word_lists.py on a small fake Hunspell dictionary (issue #76)."""

import importlib.util
from pathlib import Path

import pytest

TOOL_PATH = Path(__file__).resolve().parent.parent / "tools" / "build_word_lists.py"


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location("build_word_lists", TOOL_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_dictionary(tmp_path: Path) -> Path:
    (tmp_path / "fake.aff").write_text(
        "SET UTF-8\n"
        "PFX U Y 1\nPFX U 0 un .\n"
        "SFX S Y 2\nSFX S 0 s [^s]\nSFX S y ies [^aeiou]y\n"
        "SFX D Y 1\nSFX D 0 ed [^e]\n",
        encoding="utf-8",
    )
    (tmp_path / "fake.dic").write_text(
        "8\nwill/S\nLotte/S\nmark/DUS\nstudy/S\nzoo\nan\nextraordinarilylong\nsmall/c\n",
        encoding="utf-8",
    )
    return tmp_path / "fake.dic"


class TestBuildEnglish:
    def test_lowercase_kept_capital_dropped(self, tool, fake_dictionary: Path) -> None:
        words = tool.build_english([fake_dictionary])
        assert "will" in words
        assert not {"lotte", "Lotte", "lottes", "Lottes"} & words

    def test_affix_rules_are_expanded(self, tool, fake_dictionary: Path) -> None:
        words = tool.build_english([fake_dictionary])
        assert {"wills", "marks", "marked", "unmark", "unmarks", "studies"} <= words

    def test_length_limits_apply(self, tool, fake_dictionary: Path) -> None:
        words = tool.build_english([fake_dictionary])
        assert "an" not in words
        assert "extraordinarilylong" not in words
        assert "zoo" in words

    def test_only_in_compound_words_are_skipped(self, tool, fake_dictionary: Path) -> None:
        assert "small" not in tool.build_english([fake_dictionary])


class TestDutchAndExclusions:
    def test_dutch_list_keeps_lowercase_letters_only(self, tool, tmp_path: Path) -> None:
        wordlist = tmp_path / "wordlist.txt"
        wordlist.write_text("visser\nBos\nbos\n010\nzo\nde-boer\nkees\n", encoding="utf-8")
        assert tool.build_dutch(wordlist) == {"visser", "bos", "kees"}

    def test_exclusions_ignore_comments_and_blanks(self, tool, tmp_path: Path) -> None:
        path = tmp_path / "exclusions.txt"
        path.write_text("# a comment\nkees\n\n  Koen  # trailing\n", encoding="utf-8")
        assert tool.read_exclusions(path) == {"kees", "koen"}

    def test_written_list_has_a_source_header_and_sorted_words(
        self, tool, tmp_path: Path
    ) -> None:
        path = tmp_path / "list.txt"
        tool.write_list(path, {"zebra", "apple"}, "Test source")
        lines = path.read_text(encoding="utf-8").splitlines()
        assert lines[0].startswith("# Test source. Built ")
        assert lines[1:] == ["apple", "zebra"]
