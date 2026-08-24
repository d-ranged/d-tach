"""Tests for FolderProcessor service class."""

from pathlib import Path

import fitz
import pytest
from docx import Document

from app.services.anonymizer import Anonymizer
from app.services.file_processor import FileProcessor, FileResult, ProcessingSettings
from app.services.folder_processor import FolderProcessor, FolderSummary
from app.services.language_detector import LanguageDetector


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a DOCX file with the given paragraphs for use in tests."""
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(str(path))


def make_pdf(path: Path, lines: list[str]) -> None:
    """Create a simple PDF with the given lines for use in tests."""
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 20
    doc.save(str(path))
    doc.close()


@pytest.fixture(scope="session")
def file_processor() -> FileProcessor:
    """Single FileProcessor shared across tests (spaCy models load once)."""
    return FileProcessor(
        anonymizer=Anonymizer(),
        language_detector=LanguageDetector(),
    )


@pytest.fixture(scope="session")
def folder_processor(file_processor: FileProcessor) -> FolderProcessor:
    """Single FolderProcessor shared across tests."""
    return FolderProcessor(file_processor=file_processor)


@pytest.fixture
def settings() -> ProcessingSettings:
    """Default ProcessingSettings for tests."""
    return ProcessingSettings(language="en")


# ---------------------------------------------------------------------------
# collect_files
# ---------------------------------------------------------------------------

class TestCollectFiles:
    def test_finds_docx_and_pdf(self, tmp_path: Path, folder_processor: FolderProcessor) -> None:
        make_docx(tmp_path / "report.docx", ["Hello"])
        make_pdf(tmp_path / "notes.pdf", ["Hello"])
        (tmp_path / "readme.txt").write_text("ignore me")

        files = folder_processor.collect_files(tmp_path)

        names = {f.name for f in files}
        assert "report.docx" in names
        assert "notes.pdf" in names
        assert "readme.txt" not in names

    def test_empty_folder_returns_empty_list(self, tmp_path: Path, folder_processor: FolderProcessor) -> None:
        assert folder_processor.collect_files(tmp_path) == []

    def test_recurses_into_subfolders(self, tmp_path: Path, folder_processor: FolderProcessor) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        make_docx(tmp_path / "root.docx", ["Root"])
        make_docx(sub / "nested.docx", ["Nested"])

        files = folder_processor.collect_files(tmp_path)

        assert len(files) == 2
        names = {f.name for f in files}
        assert "root.docx" in names
        assert "nested.docx" in names

    def test_deepest_files_come_first(self, tmp_path: Path, folder_processor: FolderProcessor) -> None:
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        make_docx(tmp_path / "shallow.docx", ["Shallow"])
        make_docx(deep / "deep.docx", ["Deep"])

        files = folder_processor.collect_files(tmp_path)

        # deepest-first: deep.docx should appear before shallow.docx
        names = [f.name for f in files]
        assert names.index("deep.docx") < names.index("shallow.docx")

    def test_ignores_unsupported_extensions(self, tmp_path: Path, folder_processor: FolderProcessor) -> None:
        (tmp_path / "data.csv").write_text("a,b,c")
        (tmp_path / "image.png").write_bytes(b"\x89PNG")
        make_docx(tmp_path / "doc.docx", ["text"])

        files = folder_processor.collect_files(tmp_path)

        assert len(files) == 1
        assert files[0].name == "doc.docx"

    def test_case_insensitive_extension_match(self, tmp_path: Path, folder_processor: FolderProcessor) -> None:
        # Rename a pdf with uppercase extension by writing bytes directly
        upper = tmp_path / "UPPER.PDF"
        lower_src = tmp_path / "_tmp.pdf"
        make_pdf(lower_src, ["Hello"])
        upper.write_bytes(lower_src.read_bytes())
        lower_src.unlink()

        files = folder_processor.collect_files(tmp_path)
        assert len(files) == 1
        assert files[0].name == "UPPER.PDF"


# ---------------------------------------------------------------------------
# process (generator)
# ---------------------------------------------------------------------------

class TestProcess:
    def test_yields_result_per_file(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        make_docx(tmp_path / "a.docx", ["Hello world."])
        make_docx(tmp_path / "b.docx", ["Another doc."])

        results = list(folder_processor.process(tmp_path, settings))
        assert len(results) == 2

    def test_yields_correct_n_and_total(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        for i in range(3):
            make_docx(tmp_path / f"file{i}.docx", ["text"])

        items = list(folder_processor.process(tmp_path, settings))
        totals = [total for _, _, total in items]
        ns = [n for _, n, _ in items]

        assert all(t == 3 for t in totals)
        assert sorted(ns) == [1, 2, 3]

    def test_pii_file_anonymized(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["Contact John Smith at john@example.com"])

        results = list(folder_processor.process(tmp_path, settings))
        result, _, _ = results[0]

        assert result.status == "anonymized"

    def test_clean_file_gets_checked_status(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        make_docx(tmp_path / "clean.docx", ["This document contains no personal data."])

        results = list(folder_processor.process(tmp_path, settings))
        result, _, _ = results[0]

        assert result.status == "clean"

    def test_empty_folder_yields_nothing(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        assert list(folder_processor.process(tmp_path, settings)) == []

    def test_error_in_one_file_does_not_stop_others(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        make_docx(tmp_path / "good.docx", ["Hello world."])
        make_docx(tmp_path / "bad.docx", ["Hello world."])

        call_count = 0

        original_process = folder_processor._file_processor.process

        def patched_process(path, s, output_path_override=None):
            nonlocal call_count
            call_count += 1
            if path.name == "bad.docx":
                raise RuntimeError("Simulated processing failure")
            return original_process(path, s, output_path_override)

        monkeypatch.setattr(folder_processor._file_processor, "process", patched_process)

        results = list(folder_processor.process(tmp_path, settings))

        assert len(results) == 2
        assert call_count == 2

        statuses = {r.source_path.name: r.status for r, _, _ in results}
        assert statuses["bad.docx"] == "error"

    def test_error_result_has_error_message(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings,
        monkeypatch: pytest.MonkeyPatch
    ) -> None:
        make_docx(tmp_path / "bad.docx", ["text"])

        def raise_error(path, s, output_path_override=None):
            raise ValueError("Something went wrong")

        monkeypatch.setattr(folder_processor._file_processor, "process", raise_error)

        results = list(folder_processor.process(tmp_path, settings))
        result, _, _ = results[0]

        assert result.status == "error"
        assert "Something went wrong" in result.error_message


# ---------------------------------------------------------------------------
# summarise
# ---------------------------------------------------------------------------

class TestSummarise:
    def _make_result(self, status: str) -> FileResult:
        return FileResult(status=status, source_path=Path("dummy.docx"))

    def test_empty_results(self, folder_processor: FolderProcessor) -> None:
        summary = folder_processor.summarise([])
        assert summary.total == 0
        assert summary.anonymized == 0
        assert summary.clean == 0
        assert summary.skipped == 0
        assert summary.errors == 0

    def test_counts_anonymized(self, folder_processor: FolderProcessor) -> None:
        results = [self._make_result("anonymized")] * 3
        summary = folder_processor.summarise(results)
        assert summary.total == 3
        assert summary.anonymized == 3

    def test_counts_clean(self, folder_processor: FolderProcessor) -> None:
        results = [self._make_result("clean")] * 2
        summary = folder_processor.summarise(results)
        assert summary.clean == 2

    def test_counts_skipped(self, folder_processor: FolderProcessor) -> None:
        results = [self._make_result("skipped")] * 1
        summary = folder_processor.summarise(results)
        assert summary.skipped == 1

    def test_counts_errors(self, folder_processor: FolderProcessor) -> None:
        results = [self._make_result("error")] * 2
        summary = folder_processor.summarise(results)
        assert summary.errors == 2

    def test_mixed_results(self, folder_processor: FolderProcessor) -> None:
        results = [
            self._make_result("anonymized"),
            self._make_result("anonymized"),
            self._make_result("clean"),
            self._make_result("skipped"),
            self._make_result("error"),
        ]
        summary = folder_processor.summarise(results)
        assert summary.total == 5
        assert summary.anonymized == 2
        assert summary.clean == 1
        assert summary.skipped == 1
        assert summary.errors == 1

    def test_results_stored_in_summary(self, folder_processor: FolderProcessor) -> None:
        results = [self._make_result("clean"), self._make_result("anonymized")]
        summary = folder_processor.summarise(results)
        assert len(summary.results) == 2

    def test_returns_folder_summary_type(self, folder_processor: FolderProcessor) -> None:
        summary = folder_processor.summarise([])
        assert isinstance(summary, FolderSummary)


# ---------------------------------------------------------------------------
# consolidated keyref CSV (Step 5)
# ---------------------------------------------------------------------------

class TestConsolidatedKeyref:
    def test_csv_created_when_key_reference_enabled(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["My name is John Smith and I live here."])
        settings_kr = ProcessingSettings(key_reference_enabled=True)
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings_kr)]
        summary = folder_processor.summarise(results, folder=tmp_path, key_reference_enabled=True)
        assert summary.keyref_csv_path is not None
        assert summary.keyref_csv_path.exists()
        assert summary.keyref_csv_path.name == f"KEYREF_{tmp_path.name}.csv"

    def test_csv_contains_replacement_mapping(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["My name is John Smith and I live here."])
        settings_kr = ProcessingSettings(key_reference_enabled=True)
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings_kr)]
        summary = folder_processor.summarise(results, folder=tmp_path, key_reference_enabled=True)
        assert summary.keyref_csv_path is not None
        content = summary.keyref_csv_path.read_text(encoding="utf-8")
        assert "Placeholder" in content
        assert "Original value" in content
        assert "John Smith" in content

    def test_csv_has_header_row(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        import csv as csv_mod
        make_docx(tmp_path / "pii.docx", ["My name is John Smith."])
        settings_kr = ProcessingSettings(key_reference_enabled=True)
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings_kr)]
        summary = folder_processor.summarise(results, folder=tmp_path, key_reference_enabled=True)
        assert summary.keyref_csv_path is not None
        with summary.keyref_csv_path.open(encoding="utf-8") as f:
            reader = csv_mod.reader(f)
            header = next(reader)
        assert header == ["Placeholder", "Original value"]

    def test_no_csv_when_key_reference_disabled(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["My name is John Smith."])
        results = [r for r, _, _ in folder_processor.process(tmp_path, ProcessingSettings())]
        summary = folder_processor.summarise(results, folder=tmp_path, key_reference_enabled=False)
        assert summary.keyref_csv_path is None

    def test_no_csv_when_no_replacements(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "clean.docx", ["No personal data here at all."])
        settings_kr = ProcessingSettings(key_reference_enabled=True)
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings_kr)]
        summary = folder_processor.summarise(results, folder=tmp_path, key_reference_enabled=True)
        assert summary.keyref_csv_path is None

    def test_per_file_keyref_txt_suppressed_in_folder_mode(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["My name is John Smith."])
        settings_kr = ProcessingSettings(key_reference_enabled=True)
        list(folder_processor.process(tmp_path, settings_kr))
        # Per-file KEYREF_ txt should not exist in folder mode
        keyref_txts = list(tmp_path.glob("KEYREF_*.txt"))
        assert keyref_txts == []

    def test_replacements_aggregated_from_multiple_files(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "file1.docx", ["My name is John Smith."])
        make_docx(tmp_path / "file2.docx", ["Contact alice@example.com for info."])
        settings_kr = ProcessingSettings(key_reference_enabled=True)
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings_kr)]
        summary = folder_processor.summarise(results, folder=tmp_path, key_reference_enabled=True)
        assert summary.keyref_csv_path is not None
        content = summary.keyref_csv_path.read_text(encoding="utf-8")
        assert "John Smith" in content
        assert "alice@example.com" in content


# ---------------------------------------------------------------------------
# subfolder output mode (Step 7)
# ---------------------------------------------------------------------------

class TestSubfolderOutputMode:
    def test_anonymized_dir_created(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder")
        list(folder_processor.process(tmp_path, settings))
        assert (tmp_path / "anonymized").is_dir()

    def test_output_file_has_original_name(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "report.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder")
        list(folder_processor.process(tmp_path, settings))
        assert (tmp_path / "anonymized" / "report.docx").exists()
        assert not any((tmp_path / "anonymized").glob("ANON_*"))

    def test_clean_file_copied_to_anonymized(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "clean.docx", ["No personal data here at all."])
        settings = ProcessingSettings(output_mode="subfolder")
        list(folder_processor.process(tmp_path, settings))
        assert (tmp_path / "anonymized" / "clean.docx").exists()

    def test_original_folder_untouched(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "report.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder")
        list(folder_processor.process(tmp_path, settings))
        assert not any(tmp_path.glob("ANON_*"))
        assert not any(tmp_path.glob("CHECKED_*"))

    def test_subfolder_structure_mirrored(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        make_docx(sub / "nested.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder")
        list(folder_processor.process(tmp_path, settings))
        assert (tmp_path / "anonymized" / "sub" / "nested.docx").exists()

    def test_anonymized_dir_skipped_in_collect_files(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        (tmp_path / "anonymized").mkdir()
        make_docx(tmp_path / "anonymized" / "existing.docx", ["text"])
        make_docx(tmp_path / "real.docx", ["text"])
        files = folder_processor.collect_files(tmp_path)
        names = [f.name for f in files]
        assert "real.docx" in names
        assert "existing.docx" not in names

    def test_keyref_csv_inside_anonymized_in_subfolder_mode(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["My name is John Smith."])
        settings_kr = ProcessingSettings(output_mode="subfolder", key_reference_enabled=True)
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings_kr)]
        summary = folder_processor.summarise(
            results, folder=tmp_path, key_reference_enabled=True, output_mode="subfolder"
        )
        assert summary.keyref_csv_path is not None
        assert summary.keyref_csv_path.parent == tmp_path / "anonymized"

    def test_subfolder_output_path_helper(
        self, folder_processor: FolderProcessor, tmp_path: Path
    ) -> None:
        chosen = tmp_path / "chosen"
        chosen.mkdir()
        sub = chosen / "sub"
        sub.mkdir()
        file = sub / "report.docx"
        result = folder_processor._subfolder_output_path(file, chosen)
        assert result == chosen / "anonymized" / "sub" / "report.docx"

    def test_prefix_mode_unchanged(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "pii.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="prefix")
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings)]
        result = results[0]
        assert result.status == "anonymized"
        assert result.output_path is not None
        assert result.output_path.name.startswith("ANON_")


# ---------------------------------------------------------------------------
# folder name anonymization (issue #49)
# ---------------------------------------------------------------------------

class TestFolderRenaming:
    """Folder names inside the anonymized/ output directory are renamed when
    check_file_names is enabled in subfolder output mode (issue #49)."""

    def test_folder_name_with_pii_renamed_in_output(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        """Subfolder named after a person detected in document content is renamed."""
        student_dir = tmp_path / "John_Smith"
        student_dir.mkdir()
        make_docx(student_dir / "report.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder", check_file_names=True)
        list(folder_processor.process(tmp_path, settings))
        anonymized_root = tmp_path / "anonymized"
        output_folder_names = [p.name for p in anonymized_root.iterdir() if p.is_dir()]
        assert "John_Smith" not in output_folder_names

    def test_source_folder_not_renamed(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        """Source directories are never modified — only the anonymized/ output is renamed."""
        student_dir = tmp_path / "John_Smith"
        student_dir.mkdir()
        make_docx(student_dir / "report.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder", check_file_names=True)
        list(folder_processor.process(tmp_path, settings))
        assert student_dir.exists(), "Source folder must not be renamed or deleted"

    def test_folder_renaming_disabled_without_check_file_names(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        """When check_file_names is off, output folder names are preserved as-is."""
        student_dir = tmp_path / "John_Smith"
        student_dir.mkdir()
        make_docx(student_dir / "report.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder", check_file_names=False)
        list(folder_processor.process(tmp_path, settings))
        assert (tmp_path / "anonymized" / "John_Smith").exists()

    def test_folder_renaming_disabled_in_prefix_mode(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        """Folder renaming is not attempted in prefix mode (source folders stay intact)."""
        student_dir = tmp_path / "John_Smith"
        student_dir.mkdir()
        make_docx(student_dir / "report.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="prefix", check_file_names=True)
        list(folder_processor.process(tmp_path, settings))
        assert student_dir.exists()

    def test_nested_folders_renamed_deepest_first(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        """Deep subfolder renamed before its parent — paths remain valid throughout."""
        outer = tmp_path / "John_Smith"
        inner = outer / "Documents"
        inner.mkdir(parents=True)
        make_docx(inner / "report.docx", ["My name is John Smith."])
        settings = ProcessingSettings(output_mode="subfolder", check_file_names=True)
        list(folder_processor.process(tmp_path, settings))
        anonymized_root = tmp_path / "anonymized"
        # No path component should still be "John_Smith"
        for p in anonymized_root.rglob("*"):
            assert "John_Smith" not in p.name


# ---------------------------------------------------------------------------
# pass-through extensions (issue #58)
# ---------------------------------------------------------------------------

class TestPassThroughExtensions:
    def test_normalize_extensions_adds_leading_dot(self) -> None:
        from app.services.folder_processor import normalize_extensions
        assert normalize_extensions("sql, .yml, DBML") == [".sql", ".yml", ".dbml"]

    def test_normalize_extensions_empty_input(self) -> None:
        from app.services.folder_processor import normalize_extensions
        assert normalize_extensions("") == []

    def test_pass_through_file_collected(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        (tmp_path / "script.sql").write_text("SELECT 1;")
        files = folder_processor.collect_files(tmp_path, frozenset({".sql"}))
        assert tmp_path / "script.sql" in files

    def test_pass_through_disabled_by_default(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        (tmp_path / "script.sql").write_text("SELECT 1;")
        files = folder_processor.collect_files(tmp_path)
        assert files == []

    def test_pass_through_copied_in_subfolder_mode(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        (tmp_path / "script.sql").write_text("SELECT 1;")
        settings = ProcessingSettings(output_mode="subfolder", pass_through_extensions=[".sql"])
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings)]
        assert len(results) == 1
        assert results[0].status == "copied"
        copied_path = tmp_path / "anonymized" / "script.sql"
        assert copied_path.exists()
        assert copied_path.read_text() == "SELECT 1;"
        assert (tmp_path / "script.sql").exists()  # source untouched

    def test_pass_through_copied_in_prefix_mode(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        (tmp_path / "script.sql").write_text("SELECT 1;")
        settings = ProcessingSettings(output_mode="prefix", pass_through_extensions=[".sql"])
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings)]
        assert len(results) == 1
        assert results[0].status == "copied"
        copied_path = tmp_path / "anonymized" / "script.sql"
        assert copied_path.exists()
        assert copied_path.read_text() == "SELECT 1;"

    def test_pass_through_preserves_directory_structure(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "model.dbml").write_text("Table x {}")
        settings = ProcessingSettings(output_mode="subfolder", pass_through_extensions=[".dbml"])
        list(folder_processor.process(tmp_path, settings))
        assert (tmp_path / "anonymized" / "sub" / "model.dbml").exists()

    def test_pass_through_alongside_scanned_files(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        make_docx(tmp_path / "report.docx", ["My name is John Smith."])
        (tmp_path / "data.sql").write_text("SELECT 1;")
        settings = ProcessingSettings(output_mode="subfolder", pass_through_extensions=[".sql"])
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings)]
        statuses = {r.source_path.name: r.status for r in results}
        assert statuses["report.docx"] == "anonymized"
        assert statuses["data.sql"] == "copied"

    def test_unrelated_extension_still_skipped(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        (tmp_path / "data.csv").write_text("a,b,c")
        settings = ProcessingSettings(output_mode="subfolder", pass_through_extensions=[".sql"])
        results = [r for r, _, _ in folder_processor.process(tmp_path, settings)]
        assert results == []

    def test_summarise_counts_copied_distinctly(
        self, folder_processor: FolderProcessor
    ) -> None:
        results = [
            FileResult(status="copied", source_path=Path("a.sql")),
            FileResult(status="anonymized", source_path=Path("b.docx")),
        ]
        summary = folder_processor.summarise(results)
        assert summary.copied == 1
        assert summary.anonymized == 1

    def test_folder_renaming_applies_with_pass_through_only_in_prefix_mode(
        self, tmp_path: Path, folder_processor: FolderProcessor
    ) -> None:
        """check_file_names still renames anonymized/ output folders even when
        the only content is pass-through files copied in prefix mode, since
        renaming operates on the output tree regardless of file type."""
        student_dir = tmp_path / "John_Smith"
        student_dir.mkdir()
        (student_dir / "notes.sql").write_text("SELECT 1;")
        settings = ProcessingSettings(
            output_mode="prefix", check_file_names=True, pass_through_extensions=[".sql"],
        )
        list(folder_processor.process(tmp_path, settings))
        anonymized_root = tmp_path / "anonymized"
        output_folder_names = [p.name for p in anonymized_root.iterdir() if p.is_dir()]
        assert "John_Smith" not in output_folder_names
        assert student_dir.exists()  # source untouched


# ---------------------------------------------------------------------------
# rename_in_place ("Rename names only" mode — issue #68)
# ---------------------------------------------------------------------------

class TestRenameInPlace:
    def test_renames_file_with_pii_in_stem(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        make_docx(tmp_path / "John_Smith_report.docx", ["Just some notes, nothing sensitive here."])

        list(folder_processor.rename_in_place(tmp_path, settings))

        remaining = {p.name for p in tmp_path.iterdir()}
        assert "John_Smith_report.docx" not in remaining
        assert len(remaining) == 1

    def test_file_content_is_never_touched(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        original_text = "My name is John Smith and this text should stay exactly as-is."
        make_docx(tmp_path / "John_Smith.docx", [original_text])

        list(folder_processor.rename_in_place(tmp_path, settings))

        renamed = next(tmp_path.iterdir())
        doc = Document(str(renamed))
        assert doc.paragraphs[0].text == original_text

    def test_no_anonymized_output_tree_created(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        make_docx(tmp_path / "John_Smith.docx", ["Notes."])

        list(folder_processor.rename_in_place(tmp_path, settings))

        assert not (tmp_path / "anonymized").exists()

    def test_clean_filename_left_unchanged(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        make_docx(tmp_path / "quarterly_report.docx", ["Nothing sensitive."])

        list(folder_processor.rename_in_place(tmp_path, settings))

        assert (tmp_path / "quarterly_report.docx").exists()

    def test_nested_folder_with_pii_name_is_renamed(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        student_dir = tmp_path / "John_Smith"
        student_dir.mkdir()
        make_docx(student_dir / "notes.docx", ["Nothing sensitive."])

        list(folder_processor.rename_in_place(tmp_path, settings))

        remaining_dirs = [p.name for p in tmp_path.iterdir() if p.is_dir()]
        assert "John_Smith" not in remaining_dirs
        assert len(remaining_dirs) == 1

    def test_nested_file_survives_parent_folder_rename(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        student_dir = tmp_path / "John_Smith"
        student_dir.mkdir()
        original_text = "Contents that must survive the rename untouched."
        make_docx(student_dir / "notes.docx", [original_text])

        list(folder_processor.rename_in_place(tmp_path, settings))

        renamed_dir = next(p for p in tmp_path.iterdir() if p.is_dir())
        nested_files = list(renamed_dir.iterdir())
        assert len(nested_files) == 1
        doc = Document(str(nested_files[0]))
        assert doc.paragraphs[0].text == original_text

    def test_any_extension_is_included_not_just_supported_types(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        (tmp_path / "John_Smith.sql").write_text("SELECT 1;")

        list(folder_processor.rename_in_place(tmp_path, settings))

        remaining = {p.name for p in tmp_path.iterdir()}
        assert "John_Smith.sql" not in remaining

    def test_empty_folder_produces_no_results(
        self, tmp_path: Path, folder_processor: FolderProcessor, settings: ProcessingSettings
    ) -> None:
        assert list(folder_processor.rename_in_place(tmp_path, settings)) == []
