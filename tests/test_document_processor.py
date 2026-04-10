"""Tests for DocumentProcessor service class."""

from pathlib import Path

import pytest
from docx import Document

from app.services.document_processor import DocumentProcessor


def make_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a DOCX file with the given paragraphs for use in tests."""
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(str(path))


@pytest.fixture
def processor() -> DocumentProcessor:
    return DocumentProcessor()


class TestLoadDocx:
    def test_extracts_paragraph_text(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        docx_path = tmp_path / "test.docx"
        make_docx(docx_path, ["Hello world.", "Second paragraph."])
        text, _ = processor.load_docx(docx_path)
        assert "Hello world." in text
        assert "Second paragraph." in text

    def test_returns_document_object(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        docx_path = tmp_path / "test.docx"
        make_docx(docx_path, ["Content here."])
        _, doc = processor.load_docx(docx_path)
        assert hasattr(doc, "paragraphs") and hasattr(doc, "save")

    def test_empty_paragraphs_excluded(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        docx_path = tmp_path / "test.docx"
        make_docx(docx_path, ["", "Non-empty paragraph.", ""])
        text, _ = processor.load_docx(docx_path)
        assert text.strip() == "Non-empty paragraph."


class TestSaveDocxWithReplacements:
    def test_replacement_applied_to_output(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.docx"
        dest = tmp_path / "output.docx"
        make_docx(source, ["My name is John Smith."])
        _, doc = processor.load_docx(source)

        processor.save_docx_with_replacements(
            doc, dest, {"John Smith": "PERSON_1"}
        )

        result_text, _ = processor.load_docx(dest)
        assert "PERSON_1" in result_text
        assert "John Smith" not in result_text

    def test_original_file_not_modified(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.docx"
        dest = tmp_path / "output.docx"
        make_docx(source, ["My name is John Smith."])
        _, doc = processor.load_docx(source)
        processor.save_docx_with_replacements(doc, dest, {"John Smith": "PERSON_1"})

        # Reload the original and verify it is unchanged
        original_text, _ = processor.load_docx(source)
        assert "John Smith" in original_text

    def test_multiple_replacements_applied(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.docx"
        dest = tmp_path / "output.docx"
        make_docx(source, ["Contact John Smith at john@example.com."])
        _, doc = processor.load_docx(source)

        processor.save_docx_with_replacements(
            doc, dest, {"John Smith": "PERSON_1", "john@example.com": "EMAIL_1"}
        )

        result_text, _ = processor.load_docx(dest)
        assert "PERSON_1" in result_text
        assert "EMAIL_1" in result_text

    def test_output_saved_to_dest_path(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.docx"
        dest = tmp_path / "ANON_source.docx"
        make_docx(source, ["Some text."])
        _, doc = processor.load_docx(source)
        processor.save_docx_with_replacements(doc, dest, {})
        assert dest.exists()
