"""Matching rules for lone first names and surnames, shared by class list import and detection.

A name that is only two letters (An, En, El), or that is also an ordinary word
(Will, Mark, Bos), would corrupt a document if it were matched like any other
name. The rule for a name is decided once, on import, and stored with the
known value so the word lists are not checked on every document.
"""

import re
from functools import lru_cache
from pathlib import Path
from typing import Final, Optional

from app.app_paths import bundle_dir

RULE_SHORT: Final[str] = "short"      # 2 letters or fewer, never matched alone
RULE_CAPITAL: Final[str] = "capital"  # ordinary word, matched only with a capital first letter
RULE_ANY: Final[str] = "any"          # matched however it is written

RULES: Final[tuple[str, ...]] = (RULE_SHORT, RULE_CAPITAL, RULE_ANY)

MAX_SHORT_NAME_LENGTH: Final[int] = 2

# Shipped with the code: the project root from source, PyInstaller's bundle frozen.
WORD_LIST_DIR: Final[Path] = bundle_dir() / "app" / "data"
WORD_LIST_FILES: Final[tuple[str, ...]] = ("ordinary_words_en.txt", "ordinary_words_nl.txt")

_COMMENT_PREFIX: Final[str] = "#"


@lru_cache(maxsize=1)
def ordinary_words() -> frozenset[str]:
    """Return the English and Dutch ordinary words as one set, loaded once on first use.

    Both lists are always checked, whatever languages are installed, so a rule
    set on import never goes stale when a language is added.
    """
    words: set[str] = set()
    for file_name in WORD_LIST_FILES:
        path = WORD_LIST_DIR / file_name
        for line in path.read_text(encoding="utf-8").splitlines():
            if line and not line.startswith(_COMMENT_PREFIX):
                words.add(line)
    return frozenset(words)


def classify_name(value: str) -> str:
    """Return the matching rule for a first name, surname or full name.

    In order: more than one word is RULE_ANY (a full-word match, not a lone word),
    2 letters or fewer is RULE_SHORT, a lowercase form on either word list is
    RULE_CAPITAL, anything else is RULE_ANY.
    """
    name = value.strip()
    if len(name.split()) > 1:
        return RULE_ANY
    if len(name) <= MAX_SHORT_NAME_LENGTH:
        return RULE_SHORT
    if name.lower() in ordinary_words():
        return RULE_CAPITAL
    return RULE_ANY


def lone_name_pattern(value: str, rule: str) -> Optional[str]:
    """Return the regex body that matches value under rule, or None for RULE_SHORT.

    Presidio compiles patterns with ignore-case on. For RULE_CAPITAL the first
    letter is wrapped in (?-i:...) so only that letter is case-sensitive:
    `Will` and `WILL` match, `will` does not. The whole-word guard stays with
    the recognizer.
    """
    name = value.strip()
    if rule == RULE_SHORT or not name:
        return None
    if rule == RULE_CAPITAL:
        return f"(?-i:{re.escape(name[0].upper())}){re.escape(name[1:])}"
    return re.escape(name)
