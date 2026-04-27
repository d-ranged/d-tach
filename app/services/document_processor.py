import logging
from pathlib import Path

import fitz  # pymupdf
from docx import Document
from openpyxl import Workbook, load_workbook

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Handles DOCX, PDF, and Excel file reading and anonymized writing.

    DOCX: text extraction and run-level replacement via python-docx.
    PDF: text extraction and in-place redaction via pymupdf.
    Excel: text extraction and cell-level replacement via openpyxl.

    The original file is never written to by any method.
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
    # Excel methods
    # ------------------------------------------------------------------

    def load_xlsx(self, path: Path) -> tuple[str, Workbook]:
        """Load an Excel workbook and return its text content and the Workbook object.

        Only string cell values are included in the text. Formula cells and
        non-string cells (numbers, dates, None) are excluded. Cells within
        each row are concatenated to give the NER model enough context —
        the same approach used for DOCX table rows.
        """
        wb = load_workbook(str(path))
        text = self._extract_xlsx_text(wb)
        return text, wb

    def save_xlsx_with_replacements(
        self, wb: Workbook, dest_path: Path, replacements: dict[str, str]
    ) -> None:
        """Apply replacements to all string cells in wb and save to dest_path.

        Replacements are applied longest-first to avoid replacing a substring
        before a longer match. Formula cells and non-string cells are not touched.
        Cell formatting is preserved because only cell.value is modified.
        """
        self._apply_xlsx_replacements(wb, replacements)
        wb.save(str(dest_path))

    def save_xlsx_copy(self, wb: Workbook, dest_path: Path) -> None:
        """Save an unmodified copy of the workbook to dest_path."""
        wb.save(str(dest_path))

    # ------------------------------------------------------------------
    # Excel internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_xlsx_text(wb: Workbook) -> str:
        """Return all string cell text from all sheets, joined by newlines.

        Formula cells are excluded. Cells within each row are concatenated
        so the NER model receives enough context to identify names.
        """
        parts: list[str] = []
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                row_text = " ".join(
                    str(cell.value)
                    for cell in row
                    if isinstance(cell.value, str)
                    and not cell.value.startswith("=")
                    and cell.value.strip()
                )
                if row_text:
                    parts.append(row_text)
        return "\n".join(parts)

    @staticmethod
    def _apply_xlsx_replacements(wb: Workbook, replacements: dict[str, str]) -> None:
        """Replace all occurrences of original text in string cells across all sheets."""
        sorted_replacements = sorted(
            replacements.items(), key=lambda x: len(x[0]), reverse=True
        )
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if not isinstance(cell.value, str) or cell.value.startswith("="):
                        continue
                    new_value = cell.value
                    for original, placeholder in sorted_replacements:
                        new_value = new_value.replace(original, placeholder)
                    cell.value = new_value

    # ------------------------------------------------------------------
    # Markdown methods
    # ------------------------------------------------------------------

    def load_md(self, path: Path) -> str:
        """Load a Markdown file and return its full text content."""
        return path.read_text(encoding="utf-8")

    def save_md_with_replacements(
        self, text: str, dest_path: Path, replacements: dict[str, str]
    ) -> None:
        """Apply replacements to markdown text and save to dest_path.

        Replacements are applied longest-first to avoid replacing a substring
        before the full match (e.g. replacing 'Craig' before 'Craig Bradley').
        """
        sorted_replacements = sorted(
            replacements.items(), key=lambda x: len(x[0]), reverse=True
        )
        for original, placeholder in sorted_replacements:
            text = text.replace(original, placeholder)
        dest_path.write_text(text, encoding="utf-8")

    def save_md_copy(self, text: str, dest_path: Path) -> None:
        """Save an unmodified copy of the markdown text to dest_path."""
        dest_path.write_text(text, encoding="utf-8")

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
