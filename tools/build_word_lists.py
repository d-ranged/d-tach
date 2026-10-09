"""Build the ordinary-word lists d-tach ships in app/data/.

An "ordinary word" is a lowercase dictionary word. d-tach uses the lists to
decide whether a lone first name or surname (Will, Mark, Bos) is also an
everyday word, in which case it is only matched with a capital first letter.

Sources, downloaded by hand, this script makes no network calls:

  English: SCOWL / ESDB official Hunspell dictionaries, MIT-style licence.
    https://github.com/en-wl/wordlist/releases  (release rel-2026.02.25)
    Files: hunspell-en_US-<release>.zip and hunspell-en_GB-ise-<release>.zip.
    Unzip both; each holds a .dic and a .aff file.
  Dutch: OpenTaal wordlist.txt, BSD-3-Clause (or CC BY 3.0).
    https://github.com/OpenTaal/opentaal-wordlist  (wordlist.txt)

Command, from the repo root:

  python tools/build_word_lists.py \\
      --en-dic en_US/en_US.dic --en-dic en_GB-ise/en_GB-ise.dic \\
      --nl-wordlist opentaal/wordlist.txt \\
      --en-source "SCOWL/ESDB Hunspell en_US + en_GB-ise rel-2026.02.25" \\
      --nl-source "OpenTaal wordlist.txt 2.20.23" \\
      --exclusions tools/word_list_exclusions.txt --out app/data

For each .dic the matching .aff must sit next to it with the same stem.
Licence notices go next to the lists in app/data/ by hand, see the
LICENSE-ordinary-words-*.txt files there.

Rules, from the design on issue #76:

  - Lowercase entries only. The dictionaries hold proper nouns with a capital
    (Lotte, Thomas); dropping them is what keeps names out of the lists.
  - Letters only, 3 to 12 letters. Shorter names never reach the list because
    the short-name rule catches them first.
  - English affix rules are expanded, so "wills" and "marked" are words too.
  - Words on the exclusions file are removed: names that are also a rare word,
    which should still be matched however they are written.
"""

import argparse
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Final

MIN_WORD_LENGTH: Final[int] = 3
MAX_WORD_LENGTH: Final[int] = 12

EN_LIST_NAME: Final[str] = "ordinary_words_en.txt"
NL_LIST_NAME: Final[str] = "ordinary_words_nl.txt"

ONLY_IN_COMPOUND_FLAG: Final[str] = "c"


@dataclass
class AffixRule:
    """One Hunspell PFX or SFX line: strip, add and the condition on the word."""

    strip: str
    add: str
    condition: re.Pattern[str]


@dataclass
class AffixClass:
    """All rules that share one flag letter, plus whether prefix and suffix combine."""

    cross_product: bool
    rules: list[AffixRule] = field(default_factory=list)


class HunspellExpander:
    """Expands a Hunspell .dic file with its .aff rules into full word forms.

    Handles what the SCOWL English dictionaries use: single-letter flags,
    PFX and SFX rules with a strip, an add and a condition, and cross products
    between one prefix and one suffix. Continuation flags on an affix are
    ignored, SCOWL does not rely on them for ordinary words.
    """

    def __init__(self, aff_path: Path) -> None:
        """Read the prefix and suffix rules from aff_path."""
        self._prefixes: dict[str, AffixClass] = {}
        self._suffixes: dict[str, AffixClass] = {}
        self._read_aff(aff_path)

    def expand(self, dic_path: Path) -> set[str]:
        """Return every word form listed in dic_path, affixes applied."""
        words: set[str] = set()
        lines = dic_path.read_text(encoding="utf-8").splitlines()
        for line in lines[1:]:  # the first line is the entry count
            entry = line.split("\t")[0].strip()
            if not entry or entry.startswith("#"):
                continue
            stem, _, flags = entry.partition("/")
            if ONLY_IN_COMPOUND_FLAG in flags:
                continue
            words.add(stem)
            words.update(self._forms(stem, flags))
        return words

    def _forms(self, stem: str, flags: str) -> set[str]:
        """Return the prefixed, suffixed and combined forms of one stem."""
        suffixed = self._apply(stem, flags, self._suffixes, at_end=True)
        prefixed = self._apply(stem, flags, self._prefixes, at_end=False)
        forms = {form for form, _ in suffixed} | {form for form, _ in prefixed}
        for suffixed_form, suffix_cross in suffixed:
            if not suffix_cross:
                continue
            for prefixed_form, prefix_cross in self._apply(
                suffixed_form, flags, self._prefixes, at_end=False
            ):
                if prefix_cross:
                    forms.add(prefixed_form)
        return forms

    @staticmethod
    def _apply(
        word: str, flags: str, classes: dict[str, AffixClass], at_end: bool
    ) -> list[tuple[str, bool]]:
        """Return (new form, cross product allowed) for every rule that fits word."""
        results: list[tuple[str, bool]] = []
        for flag in flags:
            affix_class = classes.get(flag)
            if affix_class is None:
                continue
            for rule in affix_class.rules:
                if not rule.condition.search(word):
                    continue
                if at_end:
                    if rule.strip and not word.endswith(rule.strip):
                        continue
                    base = word[: len(word) - len(rule.strip)]
                    results.append((base + rule.add, affix_class.cross_product))
                else:
                    if rule.strip and not word.startswith(rule.strip):
                        continue
                    results.append((rule.add + word[len(rule.strip):], affix_class.cross_product))
        return results

    def _read_aff(self, aff_path: Path) -> None:
        """Parse PFX and SFX headers and rules out of the .aff file."""
        for line in aff_path.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 4 or parts[0] not in ("PFX", "SFX"):
                continue
            classes = self._prefixes if parts[0] == "PFX" else self._suffixes
            flag = parts[1]
            if len(parts) == 4:  # header: PFX A Y 1
                classes[flag] = AffixClass(cross_product=parts[2] == "Y")
                continue
            strip = "" if parts[2] == "0" else parts[2]
            add = "" if parts[3].split("/")[0] == "0" else parts[3].split("/")[0]
            condition = parts[4] if len(parts) > 4 else "."
            pattern = condition + "$" if parts[0] == "SFX" else "^" + condition
            classes[flag].rules.append(AffixRule(strip, add, re.compile(pattern)))


def is_list_word(word: str) -> bool:
    """Return True for a lowercase, letters-only word of 3 to 12 letters."""
    return (
        MIN_WORD_LENGTH <= len(word) <= MAX_WORD_LENGTH
        and word.isalpha()
        and word == word.lower()
    )


def read_exclusions(path: Path) -> set[str]:
    """Return the lowercase words in the exclusions file, ignoring # comments and blanks."""
    words: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        word = line.split("#")[0].strip().lower()
        if word:
            words.add(word)
    return words


def build_english(dic_paths: list[Path]) -> set[str]:
    """Return the list words from every English .dic, each expanded with its own .aff."""
    words: set[str] = set()
    for dic_path in dic_paths:
        expander = HunspellExpander(dic_path.with_suffix(".aff"))
        words |= {word for word in expander.expand(dic_path) if is_list_word(word)}
    return words


def build_dutch(wordlist_path: Path) -> set[str]:
    """Return the list words from the OpenTaal word list."""
    lines = wordlist_path.read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if is_list_word(line.strip())}


def write_list(path: Path, words: set[str], source: str) -> None:
    """Write words sorted, one per line, under a # header naming source and build date."""
    header = f"# {source}. Built {date.today().isoformat()} by tools/build_word_lists.py\n"
    path.write_text(header + "\n".join(sorted(words)) + "\n", encoding="utf-8")


def main() -> None:
    """Parse the command line, build both lists and write them to --out."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--en-dic", action="append", type=Path, required=True)
    parser.add_argument("--nl-wordlist", type=Path, required=True)
    parser.add_argument("--en-source", required=True)
    parser.add_argument("--nl-source", required=True)
    parser.add_argument("--exclusions", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    exclusions = read_exclusions(args.exclusions)
    english = build_english(args.en_dic) - exclusions
    dutch = build_dutch(args.nl_wordlist) - exclusions

    args.out.mkdir(parents=True, exist_ok=True)
    write_list(args.out / EN_LIST_NAME, english, args.en_source)
    write_list(args.out / NL_LIST_NAME, dutch, args.nl_source)
    print(f"English: {len(english)} words. Dutch: {len(dutch)} words. Excluded: {len(exclusions)}.")


if __name__ == "__main__":
    main()
