"""Writes a replacement map back into text without touching longer words.

The writers (DOCX runs, XLSX cells, Markdown, file names) put the replacement
map back as a substitution on the text. A plain str.replace would turn the
first name Eva into a hit inside "Evaluation" and Will into one on every
"will". One rule for every writer: a hit is dropped only on clear evidence that
it is part of a longer word. When in doubt, replace.
"""

import re
from typing import Final

# A letter is a word character that is not a digit or an underscore, so a
# number next to a key is fine: s1234567 is still caught in s1234567_report.
_NOT_AFTER_LETTER: Final[str] = r"(?<![^\W\d_])"
_NOT_BEFORE_LETTER: Final[str] = r"(?![^\W\d_])"


def key_pattern(key: str, flags: int = 0) -> re.Pattern[str]:
    """Return a regex for key with a letter-edge guard at each end that is a letter.

    A key that starts or ends with a non-letter (a phone number, a '+31' prefix)
    gets no guard on that side: there is no word to be part of.
    """
    pattern = re.escape(key)
    if key[:1].isalpha():
        pattern = _NOT_AFTER_LETTER + pattern
    if key[-1:].isalpha():
        pattern = pattern + _NOT_BEFORE_LETTER
    return re.compile(pattern, flags)


def replace_keys(text: str, replacements: dict[str, str], flags: int = 0) -> str:
    """Return text with every key replaced by its placeholder, longest key first.

    Longest first so 'Craig' is not replaced before 'Craig Bradley'. Matching is
    case-exact unless flags carries re.IGNORECASE.
    """
    for original, placeholder in sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True):
        if not original:
            continue
        text = key_pattern(original, flags).sub(lambda _match, p=placeholder: p, text)
    return text
