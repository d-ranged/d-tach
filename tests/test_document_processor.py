"""Tests for DocumentProcessor service class."""

from pathlib import Path

import fitz
import pytest
from docx import Document

from app.services.document_processor import DocumentProcessor


def make_docx(path: Path, paragraphs: list[str]) -> None:
    """Create a DOCX file with the given paragraphs for use in tests."""
    doc = Document()
    for text in paragraphs:
        doc.add_paragraph(text)
    doc.save(str(path))


def make_pdf(path: Path, lines: list[str]) -> None:
    """Create a simple PDF with the given lines of text for use in tests."""
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line)
        y += 20
    doc.save(str(path))
    doc.close()


@pytest.fixture
def processor() -> DocumentProcessor:
    return DocumentProcessor()


# ---------------------------------------------------------------------------
# DOCX tests
# ---------------------------------------------------------------------------


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
            doc, dest, {"John Smith": "[PERSON_1]"}
        )

        result_text, _ = processor.load_docx(dest)
        assert "[PERSON_1]" in result_text
        assert "John Smith" not in result_text

    def test_original_file_not_modified(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.docx"
        dest = tmp_path / "output.docx"
        make_docx(source, ["My name is John Smith."])
        _, doc = processor.load_docx(source)
        processor.save_docx_with_replacements(doc, dest, {"John Smith": "[PERSON_1]"})

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
            doc, dest, {"John Smith": "[PERSON_1]", "john@example.com": "[EMAIL_ADDRESS_1]"}
        )

        result_text, _ = processor.load_docx(dest)
        assert "[PERSON_1]" in result_text
        assert "[EMAIL_ADDRESS_1]" in result_text

    def test_output_saved_to_dest_path(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.docx"
        dest = tmp_path / "ANON_source.docx"
        make_docx(source, ["Some text."])
        _, doc = processor.load_docx(source)
        processor.save_docx_with_replacements(doc, dest, {})
        assert dest.exists()


# ---------------------------------------------------------------------------
# PDF tests
# ---------------------------------------------------------------------------


class TestLoadPdf:
    def test_extracts_text_from_pdf(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        pdf_path = tmp_path / "test.pdf"
        make_pdf(pdf_path, ["Hello world.", "Second line."])
        text, doc = processor.load_pdf(pdf_path)
        doc.close()
        assert "Hello world." in text
        assert "Second line." in text

    def test_returns_fitz_document(self, processor: DocumentProcessor, tmp_path: Path) -> None:
        pdf_path = tmp_path / "test.pdf"
        make_pdf(pdf_path, ["Content here."])
        _, doc = processor.load_pdf(pdf_path)
        assert isinstance(doc, fitz.Document)
        doc.close()


class TestSavePdfWithReplacements:
    def test_original_text_removed(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.pdf"
        dest = tmp_path / "output.pdf"
        make_pdf(source, ["My name is John Smith."])
        _, doc = processor.load_pdf(source)
        processor.save_pdf_with_replacements(doc, dest, {"John Smith": "[PERSON_1]"})
        doc.close()

        result_doc = fitz.open(str(dest))
        result_text = result_doc[0].get_text()
        result_doc.close()
        assert "John Smith" not in result_text

    def test_placeholder_present_in_output(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.pdf"
        dest = tmp_path / "output.pdf"
        make_pdf(source, ["My name is John Smith."])
        _, doc = processor.load_pdf(source)
        processor.save_pdf_with_replacements(doc, dest, {"John Smith": "[PERSON_1]"})
        doc.close()

        result_doc = fitz.open(str(dest))
        result_text = result_doc[0].get_text()
        result_doc.close()
        assert "[PERSON_1]" in result_text

    def test_output_file_created(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.pdf"
        dest = tmp_path / "ANON_source.pdf"
        make_pdf(source, ["Some text."])
        _, doc = processor.load_pdf(source)
        processor.save_pdf_with_replacements(doc, dest, {})
        doc.close()
        assert dest.exists()

    def test_original_file_not_modified(
        self, processor: DocumentProcessor, tmp_path: Path
    ) -> None:
        source = tmp_path / "source.pdf"
        dest = tmp_path / "output.pdf"
        make_pdf(source, ["My name is John Smith."])
        original_mtime = source.stat().st_mtime
        _, doc = processor.load_pdf(source)
        processor.save_pdf_with_replacements(doc, dest, {"John Smith": "[PERSON_1]"})
        doc.close()
        assert source.stat().st_mtime == original_mtime
