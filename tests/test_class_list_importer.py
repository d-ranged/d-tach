"""Tests for ClassListImporter service class (issues #66 and #76 — class list import)."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.class_list_importer import ClassListImporter, ColumnMappingError, ImportResult
from app.services.document_processor import DocumentProcessor


def make_roster(path: Path, headers: list[str], rows: list[list[object]]) -> None:
    """Create a roster xlsx with a header row and the given data rows."""
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    wb.save(str(path))


def triples(entries: list[dict]) -> set[tuple[str, str, str | None]]:
    """Return {(value, rule, name_part)} for the PERSON entries."""
    return {
        (e["value"], e["rule"], e.get("name_part"))
        for e in entries
        if e["entity_type"] == "PERSON"
    }


@pytest.fixture
def importer() -> ClassListImporter:
    return ClassListImporter(document_processor=DocumentProcessor())


class TestReadColumns:
    def test_returns_header_row(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name", "Student number"], [["Craig Bradley", 1234567]])
        assert importer.read_columns(roster) == ["Name", "Student number"]


class TestThreeValuesPerStudent:
    def test_full_name_only_gives_three_values(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Joris van Dijk"]])
        updated, result = importer.import_from_file(roster, {"Name": "FULL_NAME"}, [])
        assert triples(updated) == {
            ("Joris van Dijk", "any", "full"),
            ("Joris", "any", "first"),
            ("van Dijk", "any", "surname"),
        }
        assert result.added == 3

    def test_first_name_and_surname_columns_give_the_same_three(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["First", "Last"], [["Joris", "van Dijk"]])
        updated, _ = importer.import_from_file(
            roster, {"First": "FIRST_NAME", "Last": "SURNAME"}, []
        )
        assert triples(updated) == {
            ("Joris van Dijk", "any", "full"),
            ("Joris", "any", "first"),
            ("van Dijk", "any", "surname"),
        }

    def test_full_name_splits_at_the_first_word(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Anne Marie de Vries"]])
        updated, _ = importer.import_from_file(roster, {"Name": "FULL_NAME"}, [])
        assert ("Anne", "any", "first") in triples(updated)
        assert ("Marie de Vries", "any", "surname") in triples(updated)
        assert ("Anne Marie de Vries", "any", "full") in triples(updated)

    def test_two_surname_columns_are_joined_in_sheet_order(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(
            roster, ["Voornaam", "Tussenvoegsel", "Achternaam"], [["Joris", "van", "Dijk"]]
        )
        updated, _ = importer.import_from_file(
            roster,
            # Mapping order differs from the sheet order on purpose.
            {"Achternaam": "SURNAME", "Voornaam": "FIRST_NAME", "Tussenvoegsel": "SURNAME"},
            [],
        )
        assert ("van Dijk", "any", "surname") in triples(updated)
        assert ("Joris van Dijk", "any", "full") in triples(updated)

    def test_blank_tussenvoegsel_does_not_shift_rows(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(
            roster,
            ["Voornaam", "Tussenvoegsel", "Achternaam"],
            [["Lotte", None, "Vermeulen"], ["Joris", "van", "Dijk"]],
        )
        updated, _ = importer.import_from_file(
            roster,
            {"Voornaam": "FIRST_NAME", "Tussenvoegsel": "SURNAME", "Achternaam": "SURNAME"},
            [],
        )
        found = triples(updated)
        assert ("Lotte Vermeulen", "any", "full") in found
        assert ("Joris van Dijk", "any", "full") in found
        assert ("Lotte van Dijk", "any", "full") not in found

    def test_lone_name_in_full_name_column_is_stored_as_first_name(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Lotte"]])
        updated, _ = importer.import_from_file(roster, {"Name": "FULL_NAME"}, [])
        assert triples(updated) == {("Lotte", "any", "first")}

    def test_legacy_person_mapping_is_read_as_full_name(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Lotte Vermeulen"]])
        updated, _ = importer.import_from_file(roster, {"Name": "PERSON"}, [])
        assert ("Lotte Vermeulen", "any", "full") in triples(updated)

    def test_two_first_name_columns_is_an_error(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["A", "B"], [["x", "y"]])
        with pytest.raises(ColumnMappingError):
            importer.import_from_file(roster, {"A": "FIRST_NAME", "B": "FIRST_NAME"}, [])

    def test_two_full_name_columns_is_an_error(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["A", "B"], [["x y", "z w"]])
        with pytest.raises(ColumnMappingError):
            importer.import_from_file(roster, {"A": "FULL_NAME", "B": "PERSON"}, [])


class TestRules:
    def test_an_jansen(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["First", "Last"], [["An", "Jansen"]])
        updated, result = importer.import_from_file(
            roster, {"First": "FIRST_NAME", "Last": "SURNAME"}, []
        )
        assert triples(updated) == {
            ("An Jansen", "any", "full"),
            ("An", "short", "first"),
            ("Jansen", "any", "surname"),
        }
        assert result.full_name_only == 1

    def test_will_visser(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["First", "Last"], [["Will", "Visser"]])
        updated, result = importer.import_from_file(
            roster, {"First": "FIRST_NAME", "Last": "SURNAME"}, []
        )
        assert triples(updated) == {
            ("Will Visser", "any", "full"),
            ("Will", "capital", "first"),
            ("Visser", "capital", "surname"),
        }
        assert result.capital_only == 2

    def test_lotte_vermeulen(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["First", "Last"], [["Lotte", "Vermeulen"]])
        updated, _ = importer.import_from_file(
            roster, {"First": "FIRST_NAME", "Last": "SURNAME"}, []
        )
        assert ("Lotte", "any", "first") in triples(updated)
        assert ("Vermeulen", "any", "surname") in triples(updated)


class TestOtherColumns:
    def test_numeric_id_and_email_are_imported_with_rule_any(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(
            roster,
            ["Name", "Student number", "Mail"],
            [["Lotte Vermeulen", 1234567, "lotte@example.com"]],
        )
        updated, _ = importer.import_from_file(
            roster,
            {"Name": "FULL_NAME", "Student number": "NUMERIC_ID", "Mail": "EMAIL_ADDRESS"},
            [],
        )
        others = {
            (e["value"], e["entity_type"], e["rule"])
            for e in updated
            if e["entity_type"] != "PERSON"
        }
        assert others == {
            ("1234567", "NUMERIC_ID", "any"),
            ("lotte@example.com", "EMAIL_ADDRESS", "any"),
        }

    def test_ignored_columns_are_not_imported(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name", "Notes"], [["Lotte Vermeulen", "some note"]])
        updated, _ = importer.import_from_file(roster, {"Name": "FULL_NAME"}, [])
        assert "some note" not in {e["value"] for e in updated}

    def test_no_mapped_columns_imports_nothing(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Notes"], [["some note"]])
        updated, result = importer.import_from_file(roster, {}, [])
        assert result == ImportResult(added=0, already_present=0, total_known_values=0)
        assert updated == []

    def test_blank_rows_are_skipped(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Lotte Vermeulen"], [None], ["  "]])
        _, result = importer.import_from_file(roster, {"Name": "FULL_NAME"}, [])
        assert result.added == 3


class TestMerge:
    def test_manual_entry_with_the_same_value_stays(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["lotte vermeulen"]])
        existing = [
            {"value": "Lotte Vermeulen", "entity_type": "PERSON", "source": "manual", "rule": "any"}
        ]
        updated, result = importer.import_from_file(roster, {"Name": "FULL_NAME"}, existing)
        assert updated[0] == existing[0]
        assert result.already_present == 1
        assert result.added == 2

    def test_same_class_list_entry_is_left_alone(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Lotte Vermeulen"]])
        first, _ = importer.import_from_file(roster, {"Name": "FULL_NAME"}, [])
        again, result = importer.import_from_file(roster, {"Name": "FULL_NAME"}, first)
        assert again == first
        assert result == ImportResult(
            added=0, already_present=3, total_known_values=3,
            updated=0, full_name_only=0, capital_only=0,
        )

    def test_entry_imported_before_v140_is_updated(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Lotte Vermeulen"]])
        old = [
            {"value": "Lotte Vermeulen", "entity_type": "PERSON", "source": "class_list", "rule": "any"}
        ]
        updated, result = importer.import_from_file(roster, {"Name": "FULL_NAME"}, old)
        assert result.updated == 1
        assert result.added == 2
        assert updated[0]["name_part"] == "full"

    def test_changed_rule_replaces_the_class_list_entry(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["First", "Last"], [["Will", "Visser"]])
        old = [
            {
                "value": "Will", "entity_type": "PERSON", "source": "class_list",
                "rule": "any", "name_part": "first",
            }
        ]
        updated, result = importer.import_from_file(
            roster, {"First": "FIRST_NAME", "Last": "SURNAME"}, old
        )
        assert updated[0]["rule"] == "capital"
        assert result.updated == 1

    def test_students_sharing_a_first_name_give_one_value(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["First", "Last"], [["Lotte", "Vermeulen"], ["Lotte", "Jansen"]])
        updated, result = importer.import_from_file(
            roster, {"First": "FIRST_NAME", "Last": "SURNAME"}, []
        )
        assert [e["value"] for e in updated].count("Lotte") == 1
        assert result.added == 5
        assert result.already_present == 1

    def test_a_name_used_as_first_name_and_surname_is_stable_on_re_sync(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["First", "Last"], [["Kim", "Lotte"], ["Lotte", "Kim"]])
        mapping = {"First": "FIRST_NAME", "Last": "SURNAME"}
        first_run, _ = importer.import_from_file(roster, mapping, [])
        _, second = importer.import_from_file(roster, mapping, first_run)
        assert second.updated == 0
        assert second.added == 0

    def test_re_sync_only_adds_new_rows(self, importer: ClassListImporter, tmp_path: Path) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Lotte Vermeulen"]])
        mapping = {"Name": "FULL_NAME"}
        updated, _ = importer.import_from_file(roster, mapping, [])

        make_roster(roster, ["Name"], [["Lotte Vermeulen"], ["Joris van Dijk"]])
        _, result = importer.import_from_file(roster, mapping, updated)
        assert result.added == 3
        assert result.already_present == 3
        assert result.total_known_values == 6

    def test_new_entries_carry_the_class_list_source(
        self, importer: ClassListImporter, tmp_path: Path
    ) -> None:
        roster = tmp_path / "roster.xlsx"
        make_roster(roster, ["Name"], [["Lotte Vermeulen"]])
        updated, _ = importer.import_from_file(roster, {"Name": "FULL_NAME"}, [])
        assert {e["source"] for e in updated} == {"class_list"}
