"""Tests for ClassListImporter service class (issue #66 — class list import)."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.class_list_importer import ClassListImporter, ImportResult
from app.services.document_processor import DocumentProcessor


def make_roster(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    """Create a roster xlsx with a header row and the given data rows."""
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(str(path))


@pytest.fixture
def importer() -> ClassListImporter:
    return ClassListImporter(document_processor=DocumentProcessor())


class TestReadColumns:
    def test_returns_header_row(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name", "Student number"], [["Craig Bradley", 1234567]])
        assert importer.read_columns(roster) == ["Name", "Student number"]


class TestImportFromFile:
    def test_adds_new_values_with_mapped_entity_types(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(
            roster,
            ["Name", "Student number"],
            [["Craig Bradley", 1234567], ["Nick Surname", 7654321]],
        )
        updated, result = importer.import_from_file(
            roster, {"Name": "PERSON", "Student number": "NUMERIC_ID"}, []
        )
        assert result == ImportResult(added=4, already_present=0, total_known_values=4)
        values = {(v["value"], v["entity_type"], v["source"]) for v in updated}
        assert values == {
            ("Craig Bradley", "PERSON", "class_list"),
            ("Nick Surname", "PERSON", "class_list"),
            ("1234567", "NUMERIC_ID", "class_list"),
            ("7654321", "NUMERIC_ID", "class_list"),
        }

    def test_ignore_columns_are_not_imported(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name", "Notes"], [["Craig Bradley", "some note"]])
        updated, result = importer.import_from_file(roster, {"Name": "PERSON"}, [])
        assert result.added == 1
        assert [v["value"] for v in updated] == ["Craig Bradley"]

    def test_dedup_is_case_insensitive_against_existing_values(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["craig bradley"]])
        existing = [{"value": "Craig Bradley", "entity_type": "PERSON", "source": "manual"}]
        updated, result = importer.import_from_file(roster, {"Name": "PERSON"}, existing)
        assert result == ImportResult(added=0, already_present=1, total_known_values=1)
        assert updated == existing

    def test_dedup_ignores_source_of_existing_entry(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Craig Bradley"]])
        existing = [{"value": "Craig Bradley", "entity_type": "PERSON", "source": "class_list"}]
        updated, result = importer.import_from_file(roster, {"Name": "PERSON"}, existing)
        assert result.added == 0
        assert result.already_present == 1

    def test_re_sync_only_adds_new_rows(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Craig Bradley"]])
        mapping = {"Name": "PERSON"}
        updated, _ = importer.import_from_file(roster, mapping, [])

        # Simulate the roster gaining one new row before Re-sync.
        make_roster(roster, ["Name"], [["Craig Bradley"], ["Nick Surname"]])
        updated, result = importer.import_from_file(roster, mapping, updated)
        assert result == ImportResult(added=1, already_present=1, total_known_values=2)
        assert {v["value"] for v in updated} == {"Craig Bradley", "Nick Surname"}

    def test_blank_cells_are_skipped(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Craig Bradley"], [None], ["  "]])
        updated, result = importer.import_from_file(roster, {"Name": "PERSON"}, [])
        assert result.added == 1
        assert [v["value"] for v in updated] == ["Craig Bradley"]

    def test_duplicate_values_within_the_same_import_are_counted_once(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Craig Bradley"], ["Craig Bradley"]])
        updated, result = importer.import_from_file(roster, {"Name": "PERSON"}, [])
        assert result == ImportResult(added=1, already_present=1, total_known_values=1)

    def test_no_mapped_columns_imports_nothing(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Notes"], [["some note"]])
        updated, result = importer.import_from_file(roster, {}, [])
        assert result == ImportResult(added=0, already_present=0, total_known_values=0)
        assert updated == []
