import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Optional

from app.services.document_processor import DocumentProcessor
from app.services.name_rules import RULE_ANY, RULE_CAPITAL, RULE_SHORT, classify_name

logger = logging.getLogger(__name__)

FIRST_NAME_COLUMN: Final[str] = "FIRST_NAME"
SURNAME_COLUMN: Final[str] = "SURNAME"
FULL_NAME_COLUMN: Final[str] = "FULL_NAME"
NUMERIC_ID_COLUMN: Final[str] = "NUMERIC_ID"
EMAIL_COLUMN: Final[str] = "EMAIL_ADDRESS"

# A mapping saved before v1.4.0 says PERSON for the one name column: a full name.
LEGACY_NAME_COLUMN: Final[str] = "PERSON"

NAME_COLUMN_TYPES: Final[tuple[str, ...]] = (FIRST_NAME_COLUMN, SURNAME_COLUMN, FULL_NAME_COLUMN)
ALLOWED_COLUMN_TYPES: Final[tuple[str, ...]] = NAME_COLUMN_TYPES + (NUMERIC_ID_COLUMN, EMAIL_COLUMN)

PART_FULL: Final[str] = "full"
PART_FIRST: Final[str] = "first"
PART_SURNAME: Final[str] = "surname"

PERSON_ENTITY: Final[str] = "PERSON"
CLASS_LIST_SOURCE: Final[str] = "class_list"

MIN_FULL_NAME_WORDS: Final[int] = 2


class ColumnMappingError(ValueError):
    """The column mapping cannot be imported; the message is shown to the user."""


@dataclass
class ImportResult:
    """Outcome of one class list import or re-sync run."""

    added: int
    already_present: int
    total_known_values: int
    updated: int = 0
    full_name_only: int = 0
    capital_only: int = 0


class ClassListImporter:
    """Reads a class list Excel roster and merges its students into known_values.

    Delegates all Excel I/O to DocumentProcessor; this class handles the column
    mapping, the first name / surname / full name split, the matching rule of
    each name, and the merge into the existing known values.
    """

    def __init__(self, document_processor: DocumentProcessor) -> None:
        """Store the DocumentProcessor used to read the roster file."""
        self._document_processor = document_processor

    def read_columns(self, file_path: Path) -> list[str]:
        """Return the header row of the roster's active sheet."""
        return self._document_processor.read_xlsx_headers(file_path)

    def import_from_file(
        self,
        file_path: Path,
        column_mapping: dict[str, str],
        existing_known_values: list[dict],
    ) -> tuple[list[dict], ImportResult]:
        """Read the mapped columns row by row and merge the students into existing_known_values.

        column_mapping maps header -> column type (FIRST_NAME, SURNAME,
        FULL_NAME, NUMERIC_ID, EMAIL_ADDRESS; anything else is 'Ignore'). Every
        student row gives a full name, a first name and a surname, built from
        whichever columns the list has. Each name is stored with its matching
        rule and which part it is. New entries are tagged source='class_list'.

        Merging is matched on the lowercase value. A manual entry always stays.
        A class list entry with the same rule and part is left alone, one with
        a different rule or part is replaced.

        Raises ColumnMappingError when the mapping has more than one First name
        or Full name column. Returns (updated_known_values, ImportResult).
        """
        mapping = self._clean_mapping(column_mapping)
        mapped_headers = list(mapping)
        updated = list(existing_known_values)

        counts = {"added": 0, "already_present": 0, "updated": 0}
        if mapped_headers:
            index = {entry["value"].lower(): i for i, entry in enumerate(updated)}
            handled: set[str] = set()
            rows = self._document_processor.read_xlsx_rows(file_path, mapped_headers)
            for row in rows:
                for candidate in self._candidates_for_row(row, mapping):
                    self._merge(candidate, updated, index, handled, counts)

        class_list = [entry for entry in updated if entry.get("source") == CLASS_LIST_SOURCE]
        return updated, ImportResult(
            added=counts["added"],
            already_present=counts["already_present"],
            total_known_values=len(updated),
            updated=counts["updated"],
            full_name_only=sum(1 for entry in class_list if entry.get("rule") == RULE_SHORT),
            capital_only=sum(1 for entry in class_list if entry.get("rule") == RULE_CAPITAL),
        )

    @staticmethod
    def _clean_mapping(column_mapping: dict[str, str]) -> dict[str, str]:
        """Return the usable header -> column type entries, or raise ColumnMappingError."""
        mapping: dict[str, str] = {}
        for header, column_type in column_mapping.items():
            if column_type == LEGACY_NAME_COLUMN:
                column_type = FULL_NAME_COLUMN
            if column_type in ALLOWED_COLUMN_TYPES:
                mapping[header] = column_type

        types = list(mapping.values())
        if types.count(FIRST_NAME_COLUMN) > 1:
            raise ColumnMappingError("Pick at most one First name column.")
        if types.count(FULL_NAME_COLUMN) > 1:
            raise ColumnMappingError("Pick at most one Full name column.")
        return mapping

    def _candidates_for_row(
        self, row: dict[str, str], mapping: dict[str, str]
    ) -> list[dict]:
        """Return the known value entries one roster row gives, in the order they are merged."""
        candidates = self._name_candidates(row, mapping)
        for header, column_type in mapping.items():
            value = " ".join(row.get(header, "").split())
            if column_type in (NUMERIC_ID_COLUMN, EMAIL_COLUMN) and value:
                candidates.append(self._entry(value, column_type, RULE_ANY, None))
        return candidates

    def _name_candidates(self, row: dict[str, str], mapping: dict[str, str]) -> list[dict]:
        """Return the full name, first name and surname entries for one row."""
        full, first, surname = self._split_names(row, mapping)
        candidates: list[dict] = []
        if len(full.split()) >= MIN_FULL_NAME_WORDS:
            candidates.append(self._entry(full, PERSON_ENTITY, classify_name(full), PART_FULL))
        if first:
            candidates.append(self._entry(first, PERSON_ENTITY, classify_name(first), PART_FIRST))
        if surname:
            candidates.append(
                self._entry(surname, PERSON_ENTITY, classify_name(surname), PART_SURNAME)
            )
        return candidates

    @staticmethod
    def _split_names(row: dict[str, str], mapping: dict[str, str]) -> tuple[str, str, str]:
        """Return (full name, first name, surname) for one row, building what the list lacks.

        Splitting a full name is best effort: the first word is the first name
        and the rest the surname. The full name still matches whole, so nothing
        leaks when the parts are off.
        """
        def cell(header: str) -> str:
            return " ".join(row.get(header, "").split())

        first_cols = [h for h, t in mapping.items() if t == FIRST_NAME_COLUMN]
        full_cols = [h for h, t in mapping.items() if t == FULL_NAME_COLUMN]
        # Row keys follow the sheet's column order, so multi-part surnames
        # (tussenvoegsel + achternaam) join in the order they are written.
        surname_parts = [cell(h) for h in row if mapping.get(h) == SURNAME_COLUMN]

        given = cell(first_cols[0]) if first_cols else ""
        family = " ".join(part for part in surname_parts if part)
        full = cell(full_cols[0]) if full_cols else ""

        if full:
            words = full.split()
            given = given or words[0]
            family = family or " ".join(words[1:])
        else:
            full = " ".join(part for part in (given, family) if part)
        return full, given, family

    @staticmethod
    def _entry(value: str, entity_type: str, rule: str, name_part: Optional[str]) -> dict:
        """Return one class list known value entry."""
        entry = {
            "value": value,
            "entity_type": entity_type,
            "source": CLASS_LIST_SOURCE,
            "rule": rule,
        }
        if name_part:
            entry["name_part"] = name_part
        return entry

    @staticmethod
    def _merge(
        candidate: dict,
        updated: list[dict],
        index: dict[str, int],
        handled: set[str],
        counts: dict[str, int],
    ) -> None:
        """Merge one candidate into updated, counting it as added, updated or already present.

        A value met twice in one run (two students sharing a first name, or a
        name that is both a first name and a surname) is decided by its first
        occurrence, so the part does not flip back and forth.
        """
        key = candidate["value"].lower()
        position = index.get(key)
        if position is None:
            index[key] = len(updated)
            updated.append(candidate)
            handled.add(key)
            counts["added"] += 1
            return

        existing = updated[position]
        if key in handled or existing.get("source") != CLASS_LIST_SOURCE:
            counts["already_present"] += 1
            return
        handled.add(key)
        if (
            existing.get("rule", RULE_ANY) == candidate["rule"]
            and existing.get("name_part") == candidate.get("name_part")
        ):
            counts["already_present"] += 1
            return
        updated[position] = candidate
        counts["updated"] += 1
