"""Tests for FileProcessor service class."""

from pathlib import Path

import fitz
import pytest
from docx import Document

from app.services.anonymizer import Anonymizer
from app.services.file_processor import FileProcessor, ProcessingSettings
from app.services.language_detector import LanguageDetector


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


@pytest.fixture
def default_settings() -> ProcessingSettings:
    return ProcessingSettings()


class TestProcessDocx:
    def test_docx_with_pii_produces_anon_prefix(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.docx"
        make_docx(source, ["My name is John Smith and I work here."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.status == "anonymized"
        assert result.output_path is not None
        assert result.output_path.name.startswith("ANON_")

    def test_docx_with_pii_replaces_name_in_output(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.docx"
        make_docx(source, ["My name is John Smith and I work here."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.output_path is not None
        out_doc = Document(str(result.output_path))
        full_text = "\n".join(p.text for p in out_doc.paragraphs)
        assert "John Smith" not in full_text

    def test_docx_without_pii_produces_checked_prefix(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "clean.docx"
        make_docx(source, ["The results showed a fifteen percent improvement."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.status == "clean"
        assert result.output_path is not None
        assert result.output_path.name.startswith("CHECKED_")

    def test_original_file_not_modified(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.docx"
        make_docx(source, ["My name is John Smith."])
        original_mtime = source.stat().st_mtime
        file_processor.process(source, ProcessingSettings())
        assert source.stat().st_mtime == original_mtime

    def test_keyref_file_created_when_enabled(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.docx"
        make_docx(source, ["My name is John Smith."])
        settings = ProcessingSettings(key_reference_enabled=True)
        result = file_processor.process(source, settings)
        assert result.keyref_path is not None
        assert result.keyref_path.exists()
        content = result.keyref_path.read_text(encoding="utf-8")
        assert "John Smith" in content

    def test_keyref_file_not_created_when_disabled(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.docx"
        make_docx(source, ["My name is John Smith."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.keyref_path is None

    def test_unsupported_extension_returns_skipped(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        txt_file = tmp_path / "notes.txt"
        txt_file.write_text("Some text.")
        result = file_processor.process(txt_file, ProcessingSettings())
        assert result.status == "skipped"

    def test_missing_file_returns_error(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        missing = tmp_path / "does_not_exist.docx"
        result = file_processor.process(missing, ProcessingSettings())
        assert result.status == "error"
        assert result.error_message is not None

    def test_entities_found_count_is_positive_for_pii_doc(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.docx"
        make_docx(source, ["My name is John Smith."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.entities_found > 0


class TestProcessPdf:
    def test_pdf_with_pii_produces_anon_prefix(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.pdf"
        make_pdf(source, ["My name is John Smith and I work here."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.status == "anonymized"
        assert result.output_path is not None
        assert result.output_path.name.startswith("ANON_")

    def test_pdf_with_pii_removes_name_from_output(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.pdf"
        make_pdf(source, ["My name is John Smith and I work here."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.output_path is not None
        out_doc = fitz.open(str(result.output_path))
        text = out_doc[0].get_text()
        out_doc.close()
        assert "John Smith" not in text

    def test_pdf_without_pii_produces_checked_prefix(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "clean.pdf"
        make_pdf(source, ["The results showed a fifteen percent improvement."])
        result = file_processor.process(source, ProcessingSettings())
        assert result.status == "clean"
        assert result.output_path is not None
        assert result.output_path.name.startswith("CHECKED_")

    def test_pdf_original_not_modified(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.pdf"
        make_pdf(source, ["My name is John Smith."])
        original_mtime = source.stat().st_mtime
        file_processor.process(source, ProcessingSettings())
        assert source.stat().st_mtime == original_mtime

    def test_pdf_keyref_created_when_enabled(
        self, file_processor: FileProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "report.pdf"
        make_pdf(source, ["My name is John Smith."])
        result = file_processor.process(source, ProcessingSettings(key_reference_enabled=True))
        assert result.keyref_path is not None
        assert result.keyref_path.exists()
