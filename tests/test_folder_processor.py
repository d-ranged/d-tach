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

        def patched_process(path, s):
            nonlocal call_count
            call_count += 1
            if path.name == "bad.docx":
                raise RuntimeError("Simulated processing failure")
            return original_process(path, s)

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

        def raise_error(path, s):
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
