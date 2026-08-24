import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from app.services.document_processor import DocumentProcessor

logger = logging.getLogger(__name__)

ALLOWED_ENTITY_TYPES: Final[tuple[str, ...]] = ("PERSON", "NUMERIC_ID", "EMAIL_ADDRESS")

CLASS_LIST_SOURCE: Final[str] = "class_list"


@dataclass
class ImportResult:
    """Outcome of one class list import or re-sync run."""

    added: int
    already_present: int
    total_known_values: int


class ClassListImporter:
    """Reads a class list Excel roster and merges mapped columns into known_values.

    Delegates all Excel I/O to DocumentProcessor; this class only handles the
    column-mapping, normalization, and dedup logic specific to known_values.
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
        """Read mapped columns from file_path and merge new values into existing_known_values.

        column_mapping maps header -> entity_type (only entries with an entity
        type in ALLOWED_ENTITY_TYPES are read; anything else is treated as
        'Ignore' and skipped). Values are trimmed and blanks skipped. Dedup is
        case-insensitive against every existing entry regardless of source.
        New entries are tagged source='class_list'.

        Returns (updated_known_values, ImportResult).
        """
        mapped_headers = [
            header for header, entity_type in column_mapping.items()
            if entity_type in ALLOWED_ENTITY_TYPES
        ]

        updated = list(existing_known_values)
        seen_lower = {entry["value"].lower() for entry in updated}
        added = 0
        already_present = 0

        if mapped_headers:
            columns = self._document_processor.read_xlsx_columns(file_path, mapped_headers)
            for header in mapped_headers:
                entity_type = column_mapping[header]
                for raw_value in columns.get(header, []):
                    value = raw_value.strip()
                    if not value:
                        continue
                    key = value.lower()
                    if key in seen_lower:
                        already_present += 1
                        continue
                    seen_lower.add(key)
                    updated.append({
                        "value": value,
                        "entity_type": entity_type,
                        "source": CLASS_LIST_SOURCE,
                    })
                    added += 1

        return updated, ImportResult(
            added=added,
            already_present=already_present,
            total_known_values=len(updated),
        )
