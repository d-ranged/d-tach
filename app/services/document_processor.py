import logging
from pathlib import Path

from docx import Document
from docx.oxml.ns import qn

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles DOCX file reading and anonymized writing using python-docx.

    Text extraction concatenates all paragraph text from the body, tables,
    and headers/footers. Replacement is applied run-by-run, so entities that
    span a formatting boundary (split across runs) may not be replaced. This
    is a known limitation of the run-based approach.
    """

    def load_docx(self, path: Path) -> tuple[str, Document]:
        """Load a DOCX file and return its full text and the Document object.

        The Document object is used by save_docx_with_replacements. The
        original file is never written to.
        """
        doc = Document(str(path))
        text = self._extract_text(doc)
        return text, doc

    def save_docx_with_replacements(
        self, doc: Document, dest_path: Path, replacements: dict[str, str]
    ) -> None:
        """Apply replacements to all text runs in doc and save to dest_path."""
        self._apply_replacements(doc, replacements)
        doc.save(str(dest_path))

    def save_docx_copy(self, doc: Document, dest_path: Path) -> None:
        """Save an unmodified copy of doc to dest_path."""
        doc.save(str(dest_path))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _extract_text(self, doc: Document) -> str:
        """Return all readable text from the document joined by newlines."""
        parts: list[str] = []

        for para in doc.paragraphs:
            if para.text.strip():
                parts.append(para.text)

        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        if para.text.strip():
                            parts.append(para.text)

        for section in doc.sections:
            for para in section.header.paragraphs:
                if para.text.strip():
                    parts.append(para.text)
            for para in section.footer.paragraphs:
                if para.text.strip():
                    parts.append(para.text)

        return "\n".join(parts)

    def _apply_replacements(self, doc: Document, replacements: dict[str, str]) -> None:
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
