import logging
from pathlib import Path

import fitz  # pymupdf
from docx import Document

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles DOCX and PDF file reading and anonymized writing.

    DOCX: text extraction and run-level replacement via python-docx.
    PDF: text extraction and in-place redaction via pymupdf.

    The original file is never written to by either method.
    """

    # ------------------------------------------------------------------
    # DOCX methods
    # ------------------------------------------------------------------

    def load_docx(self, path: Path) -> tuple[str, Document]:
        """Load a DOCX file and return its full text and the Document object."""
        doc = Document(str(path))
        text = self._extract_docx_text(doc)
        return text, doc

    def save_docx_with_replacements(
        self, doc: Document, dest_path: Path, replacements: dict[str, str]
    ) -> None:
        """Apply replacements to all text runs in doc and save to dest_path."""
        self._apply_docx_replacements(doc, replacements)
        doc.save(str(dest_path))

    def save_docx_copy(self, doc: Document, dest_path: Path) -> None:
        """Save an unmodified copy of doc to dest_path."""
        doc.save(str(dest_path))

    # ------------------------------------------------------------------
    # PDF methods
    # ------------------------------------------------------------------

    def load_pdf(self, path: Path) -> tuple[str, fitz.Document]:
        """Load a PDF and return its full text and the fitz Document object.

        Text from all pages is joined with newlines. The fitz Document is
        used by save_pdf_with_replacements; it must be closed by the caller
        when no longer needed.
        """
        doc = fitz.open(str(path))
        text = self._extract_pdf_text(doc)
        return text, doc

    def save_pdf_with_replacements(
        self,
        doc: fitz.Document,
        dest_path: Path,
        replacements: dict[str, str],
    ) -> None:
        """Apply redaction annotations for all replacements and save to dest_path.

        Each occurrence of an original string on each page is replaced with its
        placeholder using pymupdf's redaction API. The replacement text is drawn
        at the same position in the default font. Layout of surrounding content
        is preserved.
        """
        # Sort longest first to avoid replacing a substring before the full match
        sorted_replacements = sorted(
            replacements.items(), key=lambda x: len(x[0]), reverse=True
        )

        for page in doc:
            for original, placeholder in sorted_replacements:
                rects = page.search_for(original)
                for rect in rects:
                    page.add_redact_annot(rect, text=placeholder, fontsize=11)
            page.apply_redactions()

        doc.save(str(dest_path))

    def save_pdf_copy(self, doc: fitz.Document, dest_path: Path) -> None:
        """Save an unmodified copy of the PDF to dest_path."""
        doc.save(str(dest_path))

    # ------------------------------------------------------------------
    # DOCX internal helpers
    # ------------------------------------------------------------------

    def _extract_docx_text(self, doc: Document) -> str:
        """Return all readable text from the document joined by newlines."""
        parts: list[str] = []

        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)

        for table in doc.tables:
            for row in table.rows:
                # Concatenate all cell text in the row as a single unit so the
                # NER model receives enough context to identify names. Feeding
                # each cell in isolation produces very short strings ("Nick")
                # that the spaCy medium model often fails to classify as PERSON.
                row_text = " ".join(
                    para.text.strip()
                    for cell in row.cells
                    for para in cell.paragraphs
                    if para.text.strip()
                )
                if row_text:
                    parts.append(row_text)

        for section in doc.sections:
            for para in section.header.paragraphs:
                if para.text.strip():
                    parts.append(para.text)
            for para in section.footer.paragraphs:
                if para.text.strip():
                    parts.append(para.text)

        return "\n".join(parts)

    def _apply_docx_replacements(
        self, doc: Document, replacements: dict[str, str]
    ) -> None:
        """Replace all occurrences of original text with placeholders in every run."""
        for para in doc.paragraphs:
            self._replace_in_paragraph(para, replacements)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        self._replace_in_paragraph(para, replacements)

        for section in doc.sections:
            for para in section.header.paragraphs:
                self._replace_in_paragraph(para, replacements)
            for para in section.footer.paragraphs:
                self._replace_in_paragraph(para, replacements)

    @staticmethod
    def _replace_in_paragraph(paragraph, replacements: dict[str, str]) -> None:
        """Apply all replacements to every run in a single paragraph."""
        for run in paragraph.runs:
            text = run.text
            for original, placeholder in replacements.items():
                text = text.replace(original, placeholder)
            run.text = text

    # ------------------------------------------------------------------
    # PDF internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_pdf_text(doc: fitz.Document) -> str:
        """Return all text from all pages joined by newlines."""
        parts: list[str] = []
        for page in doc:
            page_text = page.get_text()
            if page_text.strip():
                parts.append(page_text)
        return "\n".join(parts)
