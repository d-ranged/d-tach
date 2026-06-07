import csv
import logging
import re
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
        self,
        wb: Workbook,
        dest_path: Path,
        replacements: dict[str, str],
        exact_replacements: dict[str, str] | None = None,
    ) -> None:
        """Apply replacements to cells in wb and save to dest_path.

        Two passes are applied in sequence:
        1. Exact replacements (column-based): whole-cell replacement on any cell
           type where str(cell.value) exactly matches a key. Runs first so that
           already-replaced cells are not touched again by the NER pass.
        2. Substring replacements (NER-based): applied to string cells only via
           str.replace(), longest key first.

        Formula cells and None cells are skipped in both passes. Cell formatting
        is preserved because only cell.value is modified.
        """
        if exact_replacements:
            self._apply_xlsx_exact_replacements(wb, exact_replacements)
        self._apply_xlsx_replacements(wb, replacements)
        wb.save(str(dest_path))

    def extract_column_replacements(
        self, wb: Workbook, column_names: list[str], encoder=None
    ) -> tuple[dict[str, str], list[str]]:
        """Build a replacement map for the specified column names.

        Reads row 1 of each sheet as headers (case-insensitive match). For each
        matching column, collects all unique non-formula values below the header
        row and assigns placeholders.

        When encoder (a HashEncoder) is provided and hashing is enabled:
          value → [LABEL_XXXX]  where XXXX is a deterministic 4-char HMAC hash.
          Same value + same secret always produces the same placeholder.

        Without encoder (hashing off):
          value → [LABEL_N]  sequential counter, shared per label across sheets.

        Returns:
            exact_replacements: {str(original_value): placeholder}
            missing: column names not found in any sheet's row 1
        """
        requested = {
            name.strip().lower(): name.strip()
            for name in column_names
            if name.strip()
        }
        found: set[str] = set()
        exact_replacements: dict[str, str] = {}
        counters: dict[str, int] = {}

        for sheet in wb.worksheets:
            header_map: dict[str, int] = {}
            for cell in sheet[1]:
                if isinstance(cell.value, str) and cell.value.strip():
                    header_map[cell.value.strip().lower()] = cell.column

            for norm_name, orig_name in requested.items():
                if norm_name not in header_map:
                    continue
                found.add(norm_name)
                col_idx = header_map[norm_name]
                label = re.sub(r"[^A-Z0-9]", "_", orig_name.upper())
                if label not in counters:
                    counters[label] = 1

                for row in sheet.iter_rows(min_row=2, min_col=col_idx, max_col=col_idx):
                    cell = row[0]
                    if cell.value is None:
                        continue
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        continue
                    value_str = str(cell.value).strip()
                    if not value_str:
                        continue
                    if value_str not in exact_replacements:
                        if encoder:
                            exact_replacements[value_str] = f"[{label}_{encoder.encode_value(label, value_str)}]"
                        else:
                            exact_replacements[value_str] = f"[{label}_{counters[label]}]"
                            counters[label] += 1

        missing = [orig_name for norm_name, orig_name in requested.items() if norm_name not in found]
        return exact_replacements, missing

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

    @staticmethod
    def _apply_xlsx_exact_replacements(
        wb: Workbook, exact_replacements: dict[str, str]
    ) -> None:
        """Replace cells whose entire value exactly matches a key in exact_replacements.

        Applies to all cell types (string, numeric, etc.) across all sheets.
        Formula cells and None cells are skipped. The whole cell value is replaced,
        not a substring.
        """
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if cell.value is None:
                        continue
                    if isinstance(cell.value, str) and cell.value.startswith("="):
                        continue
                    value_str = str(cell.value).strip()
                    if value_str in exact_replacements:
                        cell.value = exact_replacements[value_str]

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

    # ------------------------------------------------------------------
    # Restore methods (reverse anonymization: placeholder → original)
    # ------------------------------------------------------------------

    @staticmethod
    def load_keyref_csv(path: Path) -> dict[str, str]:
        """Read a KEYREF CSV and return {placeholder: original_value}.

        Expects a two-column CSV with a header row (Placeholder, Original value)
        as produced by d-tach's consolidated keyref export.
        """
        result: dict[str, str] = {}
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            try:
                next(reader)  # skip header
            except StopIteration:
                return result
            for row in reader:
                if len(row) >= 2:
                    placeholder, original = row[0].strip(), row[1].strip()
                    if placeholder:
                        result[placeholder] = original
        return result

    def restore_docx(
        self, input_path: Path, output_path: Path, replacements: dict[str, str]
    ) -> int:
        """Replace all placeholders with originals in a DOCX.

        Returns the number of unique placeholders that were found and replaced
        at least once (not total occurrences).
        """
        doc = Document(str(input_path))
        sorted_rep = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)
        found: set[str] = set()

        def _restore_para(para) -> None:
            for run in para.runs:
                text = run.text
                for placeholder, original in sorted_rep:
                    if placeholder in text:
                        text = text.replace(placeholder, original)
                        found.add(placeholder)
                run.text = text

        for para in doc.paragraphs:
            _restore_para(para)
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    for para in cell.paragraphs:
                        _restore_para(para)
        for section in doc.sections:
            for para in section.header.paragraphs:
                _restore_para(para)
            for para in section.footer.paragraphs:
                _restore_para(para)

        doc.save(str(output_path))
        return len(found)

    def restore_xlsx(
        self, input_path: Path, output_path: Path, replacements: dict[str, str]
    ) -> int:
        """Replace all placeholders with originals in an Excel file.

        Returns the number of unique placeholders found and replaced.
        """
        wb = load_workbook(str(input_path))
        sorted_rep = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)
        found: set[str] = set()
        for sheet in wb.worksheets:
            for row in sheet.iter_rows():
                for cell in row:
                    if not isinstance(cell.value, str) or cell.value.startswith("="):
                        continue
                    text = cell.value
                    for placeholder, original in sorted_rep:
                        if placeholder in text:
                            text = text.replace(placeholder, original)
                            found.add(placeholder)
                    cell.value = text
        wb.save(str(output_path))
        return len(found)

    @staticmethod
    def restore_text(
        input_path: Path, output_path: Path, replacements: dict[str, str]
    ) -> int:
        """Replace all placeholders with originals in a text/markdown file.

        Returns the number of unique placeholders found and replaced.
        """
        text = input_path.read_text(encoding="utf-8")
        sorted_rep = sorted(replacements.items(), key=lambda x: len(x[0]), reverse=True)
        found: set[str] = set()
        for placeholder, original in sorted_rep:
            if placeholder in text:
                text = text.replace(placeholder, original)
                found.add(placeholder)
        output_path.write_text(text, encoding="utf-8")
        return len(found)
