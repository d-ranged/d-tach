import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Optional

from app.services.anonymizer import (
    Anonymizer,
    DetectedEntity,
    LOCATION_ENTITY,
    NUMERIC_ID_ENTITY,
    URL_ENTITY,
    build_numeric_id_recognizer,
)
from app.services.document_processor import DocumentProcessor
from app.services.hash_encoder import HashEncoder
from app.services.language_detector import LanguageDetector
from app.services.pattern_config import PatternConfig

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pdf", ".md", ".xlsx"})

# Entities whose matched text is shorter than this are almost certainly PDF
# ligature extraction artefacts (e.g. "ci", "fi") rather than real PII.
# Replacing them would corrupt the entire document, so they are skipped.
MIN_ENTITY_TEXT_LENGTH: int = 3


def _build_entity_list(
    anonymize_dates: bool,
    numeric_id_enabled: bool = False,
    anonymize_urls: bool = False,
    anonymize_locations: bool = False,
    known_values: Optional[list[dict]] = None,
) -> list[str]:
    """Return the entity list to pass to the Anonymizer.

    DATE_TIME is excluded unless opted in — ubiquitous in academic docs.
    LOCATION is excluded unless opted in — city/country names often carry
    meaningful context (e.g. "Deventer", "Enschede") and are not always PII.
    URL is excluded unless opted in — its recognizer overlaps with EMAIL_ADDRESS,
    causing double-detection and garbled output when both fire on the same span.
    NUMERIC_ID is included only when numeric ID detection is enabled.

    known_values entity types are always unioned in regardless of the toggles
    above — Presidio drops any ad-hoc recognizer result whose entity type is
    not in this list, so a class-list-imported NUMERIC_ID known value must
    stay detectable even when the separate digit-count Numeric ID toggle is
    off (its format may not match that toggle's configured digit count).
    """
    from app.services.anonymizer import ENTITIES
    result = list(ENTITIES) if anonymize_dates else [e for e in ENTITIES if e != "DATE_TIME"]
    if anonymize_locations:
        result.append(LOCATION_ENTITY)
    if numeric_id_enabled:
        result.append(NUMERIC_ID_ENTITY)
    if anonymize_urls:
        result.append(URL_ENTITY)
    for entry in known_values or []:
        entity_type = entry.get("entity_type") or "PERSON"
        if entity_type not in result:
            result.append(entity_type)
    return result


def compose_replacements(
    entities: list[DetectedEntity],
    encoder: Optional[HashEncoder],
) -> dict[str, str]:
    """Return a mapping of original text → replacement placeholder.

    When hashing is enabled all detected PII entities are hash-encoded:
    - PERSON: name rules (first 2 chars preserved + 4-char hash)
    - All others except DATE_TIME and NRP: full-value 4-char HMAC hash
      with a shortened label: [EMAIL_A2B3], [PHONE_C4D1], [BSN_E9F2] etc.
    - DATE_TIME and NRP: always sequential regardless of hashing setting

    When hashing is disabled all entities use the sequential placeholder
    produced by the Anonymizer: [PERSON_1], [EMAIL_ADDRESS_1] etc.

    Shared by every FileProcessor detection path (content and filenames)
    and by AI Mode's /ai/extract, so exactly one implementation exists.
    """
    replacements: dict[str, str] = {}
    for entity in entities:
        if entity.original_text in replacements:
            continue
        if len(entity.original_text) < MIN_ENTITY_TEXT_LENGTH:
            logger.warning(
                "Skipping entity %r (type=%s, length=%d) — likely a PDF "
                "ligature extraction artefact.",
                entity.original_text,
                entity.entity_type,
                len(entity.original_text),
            )
            continue
        if encoder and entity.entity_type == "PERSON":
            replacements[entity.original_text] = f"[{encoder.encode_full_name(entity.original_text)}]"
        elif encoder:
            hashed = encoder.encode_entity(entity.entity_type, entity.original_text)
            replacements[entity.original_text] = hashed if hashed else entity.placeholder
        else:
            replacements[entity.original_text] = entity.placeholder
    return replacements


class PlaceholderLedger:
    """One sequential numbering shared by every file of a folder run.

    The Anonymizer numbers placeholders from 1 in every call, so two files of the
    same folder both hand out [PERSON_1] to different people. The consolidated
    KEYREF then lists one placeholder against two values, and a restore puts the
    wrong name back. Hashing cannot do this, because the same value always
    encodes the same way.

    The ledger remembers which placeholder each original value was given and
    numbers new values per entity type, so within a run the same value always
    gets the same placeholder and different values never share one.
    """

    def __init__(self) -> None:
        """Start empty: no values seen, every counter at zero."""
        self._by_value: dict[str, str] = {}
        self._counters: dict[str, int] = {}

    def assign(self, original: str, label: str) -> str:
        """Return the run-wide placeholder for original, numbering it if new.

        label is the placeholder's type part, e.g. PERSON or EMAIL_ADDRESS.
        """
        placeholder = self._by_value.get(original)
        if placeholder is None:
            self._counters[label] = self._counters.get(label, 0) + 1
            placeholder = f"[{label}_{self._counters[label]}]"
            self._by_value[original] = placeholder
        return placeholder


@dataclass
class ProcessingSettings:
    """Configuration for a single file processing run."""

    hashing_enabled: bool = False
    secret: str = ""
    key_reference_enabled: bool = False
    check_file_names: bool = False
    language: str = "en"
    anonymize_dates: bool = False
    anonymize_locations: bool = False
    anonymize_urls: bool = False
    numeric_id_enabled: bool = False
    digit_count: int = 7
    excel_generic_enabled: bool = True
    excel_column_names: list[str] = field(default_factory=list)
    output_mode: str = "prefix"  # "prefix" | "subfolder"
    known_values: list[dict] = field(default_factory=list)
    pass_through_extensions: list[str] = field(default_factory=list)
    loading_strategy: str = "eager"  # "eager" | "lazy"
    expand_archives: bool = False
    delete_archives_after_expand: bool = False
    # Set by FolderProcessor for a run with hashing off, so numbering is shared
    # across the files of that run. None means each call numbers on its own.
    placeholder_ledger: Optional[PlaceholderLedger] = None


@dataclass
class DetectionResult:
    """Entities detected in a piece of text and their replacement placeholders."""

    entities: list[DetectedEntity]
    replacements: dict[str, str]


@dataclass
class ExtractResult:
    """The outcome of extracting and anonymizing a file's text without writing output.

    Used by AI Mode's /ai/extract — mirrors FileResult but carries anonymized
    text directly instead of an output file path, since no file is written.
    """

    status: str  # "extracted" | "clean" | "unreadable" | "error" | "skipped"
    source_path: Path
    anonymized_text: str = ""
    entities: list[DetectedEntity] = field(default_factory=list)
    replacements: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error_message: Optional[str] = None


@dataclass
class FileResult:
    """The outcome of processing a single file."""

    status: str  # "anonymized" | "clean" | "unreadable" | "error" | "skipped" | "copied"
    source_path: Path
    output_path: Optional[Path] = None
    keyref_path: Optional[Path] = None
    entities_found: int = 0
    error_message: Optional[str] = None
    warnings: list[str] = field(default_factory=list)
    replacements: dict[str, str] = field(default_factory=dict)
    # {original_text: placeholder} — used by FolderProcessor to build the consolidated keyref CSV


class FileProcessor:
    """Processes a single supported file: detects PII, writes anonymized output.

    In prefix mode (default):
    - PII detected  → ANON_{original_name}  (same directory as source)
    - No PII found  → CHECKED_{original_name}
    - Key reference → KEYREF_{original_stem}.txt  (when enabled)

    In subfolder mode (output_path_override provided by FolderProcessor):
    - Output goes to the pre-computed mirror path inside anonymized/
    - Original filename is preserved — no ANON_/CHECKED_ prefix
    """

    def __init__(
        self, anonymizer: Anonymizer, language_detector: LanguageDetector
    ) -> None:
        """Initialise with shared service instances."""
        self._anonymizer = anonymizer
        self._language_detector = language_detector
        self._doc_processor = DocumentProcessor()

    def process(
        self,
        path: Path,
        settings: ProcessingSettings,
        output_path_override: Optional[Path] = None,
    ) -> FileResult:
        """Process a single file and return a FileResult describing the outcome.

        output_path_override — when set (subfolder mode), the file is written to
        this exact path instead of a prefixed name alongside the source. The
        caller is responsible for creating the parent directory.

        A corrupt or unreadable file is caught and returned as an error result
        so callers can skip it without stopping batch processing.
        """
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            return FileResult(
                status="skipped",
                source_path=path,
                error_message=f"Unsupported file type: {path.suffix}",
            )

        ext = path.suffix.lower()
        try:
            self._language_detector.ensure_loaded(settings.language, settings.loading_strategy)
            if ext == ".docx":
                return self._process_docx(path, settings, output_path_override)
            if ext == ".md":
                return self._process_markdown(path, settings, output_path_override)
            if ext == ".xlsx":
                return self._process_xlsx(path, settings, output_path_override)
            return self._process_pdf(path, settings, output_path_override)
        except Exception as exc:
            logger.error("Failed to process %s: %s", path, exc)
            return FileResult(
                status="error",
                source_path=path,
                error_message=str(exc),
            )

    # ------------------------------------------------------------------
    # Output path resolution
    # ------------------------------------------------------------------

    def _output_path(
        self,
        source_path: Path,
        prefix: str,
        replacements: dict[str, str],
        settings: ProcessingSettings,
        language: str,
        override: Optional[Path],
    ) -> Path:
        """Return the output path for a processed file.

        In subfolder mode (override provided): apply filename anonymization to
        the override stem when check_file_names is enabled, then return the
        updated path.  No ANON_/CHECKED_ prefix is added in subfolder mode —
        the anonymized/ subfolder itself distinguishes output from source.
        In prefix mode: apply ANON_/CHECKED_ prefix, optionally running
        filename anonymization when check_file_names is enabled.
        """
        if override is not None:
            if settings.check_file_names:
                new_name = self.anonymize_filename(
                    override.stem, override.suffix,
                    replacements, settings, language,
                )
                return override.parent / new_name
            return override
        if settings.check_file_names:
            output_name = self.anonymize_filename(
                f"{prefix}{source_path.stem}", source_path.suffix,
                replacements, settings, language,
            )
        else:
            output_name = f"{prefix}{source_path.name}"
        return source_path.parent / output_name

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_docx(
        self, path: Path, settings: ProcessingSettings,
        output_path_override: Optional[Path] = None,
    ) -> FileResult:
        """Core DOCX processing logic."""
        text, doc = self._doc_processor.load_docx(path)

        if not text.strip():
            output_path = self._output_path(path, "CHECKED_", {}, settings, settings.language, output_path_override)
            self._doc_processor.save_docx_copy(doc, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        language = settings.language
        detection = self._detect(text, settings, language)

        if not detection.entities:
            output_path = self._output_path(path, "CHECKED_", {}, settings, language, output_path_override)
            self._doc_processor.save_docx_copy(doc, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        replacements = detection.replacements
        output_path = self._output_path(path, "ANON_", replacements, settings, language, output_path_override)
        self._doc_processor.save_docx_with_replacements(doc, output_path, replacements)

        keyref_path: Optional[Path] = None
        if settings.key_reference_enabled:
            keyref_path = path.parent / f"KEYREF_{path.stem}.txt"
            self._write_keyref(keyref_path, path, replacements, detection.entities)

        return FileResult(
            status="anonymized",
            source_path=path,
            output_path=output_path,
            keyref_path=keyref_path,
            entities_found=len({e.original_text for e in detection.entities}),
            replacements=replacements,
        )

    def _process_pdf(
        self, path: Path, settings: ProcessingSettings,
        output_path_override: Optional[Path] = None,
    ) -> FileResult:
        """Core PDF processing logic using pymupdf in-place redaction."""
        import fitz  # local import — only needed for PDF path

        text, doc = self._doc_processor.load_pdf(path)

        # pymupdf does not OCR, so a page with no text layer yields nothing and
        # would be written out with every real name still legible in the image.
        image_only_pages = [
            number for number, page in enumerate(doc, start=1)
            if not page.get_text().strip()
        ]

        if not text.strip():
            doc.close()
            logger.warning(
                "PDF %s yielded no extractable text — may be image-based or have non-standard encoding.", path
            )
            # Deliberately writes nothing. Everything in the output is taken to
            # be safe to pass on, and a PDF that could not be read has had no
            # PII removed at all — a scanned letter would land there with the
            # name and signature intact. An earlier version copied it in under
            # an UNREADABLE_ prefix, but subfolder mode drops the prefix, so it
            # arrived indistinguishable from properly anonymized output.
            return FileResult(
                status="unreadable",
                source_path=path,
                error_message=(
                    "PDF could not be read — may be image-based or have non-standard "
                    "encoding. Nothing was written to the output. Convert it to a "
                    "text-based PDF and retry."
                ),
            )

        warnings: list[str] = []
        if image_only_pages:
            pages = ", ".join(str(n) for n in image_only_pages)
            warnings.append(
                f"Page {pages} has no extractable text (may be image-only) and was "
                f"copied unchanged — any name shown there is still in the output. "
                f"Review manually."
                if len(image_only_pages) == 1 else
                f"Pages {pages} have no extractable text (may be image-only) and were "
                f"copied unchanged — any names shown there are still in the output. "
                f"Review manually."
            )

        language = settings.language
        detection = self._detect(text, settings, language)

        if not detection.entities:
            doc.close()
            output_path = self._output_path(path, "CHECKED_", {}, settings, language, output_path_override)
            clean_doc = fitz.open(str(path))
            self._doc_processor.save_pdf_copy(clean_doc, output_path)
            clean_doc.close()
            return FileResult(
                status="clean", source_path=path, output_path=output_path,
                warnings=warnings,
            )

        replacements = detection.replacements
        output_path = self._output_path(path, "ANON_", replacements, settings, language, output_path_override)
        self._doc_processor.save_pdf_with_replacements(doc, output_path, replacements)
        doc.close()

        keyref_path: Optional[Path] = None
        if settings.key_reference_enabled:
            keyref_path = path.parent / f"KEYREF_{path.stem}.txt"
            self._write_keyref(keyref_path, path, replacements, detection.entities)

        return FileResult(
            status="anonymized",
            source_path=path,
            output_path=output_path,
            keyref_path=keyref_path,
            entities_found=len({e.original_text for e in detection.entities}),
            replacements=replacements,
            warnings=warnings,
        )

    def _process_xlsx(
        self, path: Path, settings: ProcessingSettings,
        output_path_override: Optional[Path] = None,
    ) -> FileResult:
        """Core Excel processing logic supporting two independent anonymization modes.

        Generic NER: detects PII in string cell text (names, emails, phones).
        Column-based: replaces all values in named columns regardless of cell type,
        catching numeric identifiers invisible to NER (e.g. integer student numbers).

        If both modes are disabled the file is skipped entirely. Either mode can
        be active alone or both can run together — column-based runs first so NER
        does not produce conflicting placeholders for already-replaced cells.
        """
        if not settings.excel_generic_enabled and not settings.excel_column_names:
            return FileResult(
                status="skipped",
                source_path=path,
                error_message="Excel anonymization disabled (both modes off).",
            )

        text, wb = self._doc_processor.load_xlsx(path)
        file_warnings: list[str] = []
        encoder = HashEncoder(settings.secret) if settings.hashing_enabled else None

        # --- Column-based pass ---
        exact_replacements: dict[str, str] = {}
        if settings.excel_column_names:
            exact_replacements, missing = self._doc_processor.extract_column_replacements(
                wb, settings.excel_column_names, encoder=encoder
            )
            for col in missing:
                file_warnings.append(f"Column '{col}' not found in row 1 headers.")

        # --- NER pass ---
        substring_replacements: dict[str, str] = {}
        ner_entities: list = []
        if settings.excel_generic_enabled and text.strip():
            detection = self._detect(text, settings, settings.language)
            if detection.entities:
                substring_replacements = detection.replacements
                ner_entities = detection.entities

        # Column placeholders are numbered per file too, so they share the run's
        # numbering. Hashed ones already agree across files and are left alone.
        if encoder is None and settings.placeholder_ledger is not None:
            exact_replacements = {
                original: settings.placeholder_ledger.assign(
                    original, placeholder.strip("[]").rsplit("_", 1)[0]
                )
                for original, placeholder in exact_replacements.items()
            }

        # --- Nothing to replace → clean ---
        if not exact_replacements and not substring_replacements:
            output_path = self._output_path(path, "CHECKED_", {}, settings, settings.language, output_path_override)
            self._doc_processor.save_xlsx_copy(wb, output_path)
            return FileResult(
                status="clean",
                source_path=path,
                output_path=output_path,
                warnings=file_warnings,
            )

        # --- Build output path ---
        combined_for_names = {**substring_replacements, **exact_replacements}
        output_path = self._output_path(path, "ANON_", combined_for_names, settings, settings.language, output_path_override)

        # --- Save (exact pass first, then NER substring pass) ---
        self._doc_processor.save_xlsx_with_replacements(
            wb, output_path, substring_replacements,
            exact_replacements if exact_replacements else None,
        )

        keyref_path: Optional[Path] = None
        if settings.key_reference_enabled:
            keyref_path = path.parent / f"KEYREF_{path.stem}.txt"
            self._write_keyref(
                keyref_path, path, substring_replacements, ner_entities,
                exact_replacements if exact_replacements else None,
            )

        return FileResult(
            status="anonymized",
            source_path=path,
            output_path=output_path,
            keyref_path=keyref_path,
            entities_found=len({e.original_text for e in ner_entities}) + len(exact_replacements),
            warnings=file_warnings,
            replacements={**substring_replacements, **exact_replacements},
        )

    def _process_markdown(
        self, path: Path, settings: ProcessingSettings,
        output_path_override: Optional[Path] = None,
    ) -> FileResult:
        """Core Markdown processing logic.

        Markdown files are treated as plain text: the full content is fed to
        the anonymizer and replacements are written back with str.replace().
        Markdown syntax is preserved because PII replacements only touch the
        matched text spans, not surrounding formatting characters.
        """
        text = self._doc_processor.load_md(path)

        if not text.strip():
            output_path = self._output_path(path, "CHECKED_", {}, settings, settings.language, output_path_override)
            self._doc_processor.save_md_copy(text, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        language = settings.language
        detection = self._detect(text, settings, language)

        if not detection.entities:
            output_path = self._output_path(path, "CHECKED_", {}, settings, language, output_path_override)
            self._doc_processor.save_md_copy(text, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        replacements = detection.replacements
        output_path = self._output_path(path, "ANON_", replacements, settings, language, output_path_override)
        self._doc_processor.save_md_with_replacements(text, output_path, replacements)

        keyref_path: Optional[Path] = None
        if settings.key_reference_enabled:
            keyref_path = path.parent / f"KEYREF_{path.stem}.txt"
            self._write_keyref(keyref_path, path, replacements, detection.entities)

        return FileResult(
            status="anonymized",
            source_path=path,
            output_path=output_path,
            keyref_path=keyref_path,
            entities_found=len({e.original_text for e in detection.entities}),
            replacements=replacements,
        )

    def _detect(
        self, text: str, settings: ProcessingSettings, language: str
    ) -> DetectionResult:
        """Run entity detection and build the replacement map for already-extracted text.

        The shared "detect + build replacements" step behind every _process_*
        method and AI Mode's extract_anonymized_text, so detection logic exists
        in exactly one place.
        """
        entities = _build_entity_list(
            settings.anonymize_dates, settings.numeric_id_enabled,
            settings.anonymize_urls, settings.anonymize_locations, settings.known_values,
        )
        ad_hoc = self._build_ad_hoc_recognizers(settings, language)
        result = self._anonymizer.anonymize(text, language, entities=entities, ad_hoc_recognizers=ad_hoc)
        encoder = HashEncoder(settings.secret) if settings.hashing_enabled else None
        replacements = compose_replacements(result.entities, encoder)
        if encoder is None and settings.placeholder_ledger is not None:
            types = {e.original_text: e.entity_type for e in result.entities}
            replacements = {
                original: settings.placeholder_ledger.assign(original, types[original])
                for original in replacements
            }

        # The Anonymizer numbers placeholders sequentially, but compose_replacements
        # is what decides the token that actually lands in the text. With hashing on
        # the two disagree, and an entity list still reporting [PERSON_1] describes a
        # placeholder that appears nowhere in the output. Worse, [PERSON_1] means a
        # different person in every document, so anything reading the entity list to
        # identify subjects across a folder merges them — the exact confusion hashing
        # exists to prevent. Report what was actually written.
        for entity in result.entities:
            entity.placeholder = replacements.get(entity.original_text, entity.placeholder)

        return DetectionResult(entities=result.entities, replacements=replacements)

    def _build_ad_hoc_recognizers(
        self, settings: ProcessingSettings, language: str
    ) -> list:
        """Return ad-hoc recognizers for this processing run.

        Known values are prepended first (confidence 0.99) so they take priority
        over NER. NumericIdRecognizer is appended when numeric ID detection is on.
        """
        from app.services.anonymizer import build_known_value_recognizers
        recognizers: list = []
        if settings.known_values:
            recognizers.extend(build_known_value_recognizers(settings.known_values, language))
        if settings.numeric_id_enabled:
            config = PatternConfig(digit_count=settings.digit_count)
            recognizers.append(build_numeric_id_recognizer(config, language))
        return recognizers

    def anonymize_filename(
        self,
        stem: str,
        suffix: str,
        content_replacements: dict[str, str],
        settings: ProcessingSettings,
        language: str,
    ) -> str:
        """Return an anonymized filename by checking the stem for PII.

        First applies content_replacements (names found in the document body)
        using case-insensitive matching, then runs the anonymizer on whatever
        remains to catch any additional entities.
        """
        new_stem, _detected = self._anonymize_stem(stem, content_replacements, settings, language)
        return new_stem + suffix

    def _anonymize_stem(
        self,
        stem: str,
        content_replacements: dict[str, str],
        settings: ProcessingSettings,
        language: str,
    ) -> tuple[str, dict[str, str]]:
        """Return (anonymized stem, replacements newly detected directly in the stem).

        Case-insensitive matching against content_replacements is necessary
        because filenames often use different capitalisation than the text in
        the document body (e.g. 'nick_surname' in a filename vs 'Nick Surname'
        detected in the text). The replacement placeholder is always written in
        its original form (uppercase entity type + counter, or hash-encoded
        for PERSON). The detected-in-stem replacements are returned separately
        so callers (e.g. rename-only mode, which has no document content to
        scan) can build a KEYREF from filename-only detections.
        """
        # Treat underscores and hyphens as spaces for analysis
        readable = re.sub(r"[_\-]+", " ", stem)

        # Apply known content replacements first using case-insensitive matching,
        # sorted longest-first to avoid replacing a substring before the full match.
        for original, placeholder in sorted(
            content_replacements.items(), key=lambda x: len(x[0]), reverse=True
        ):
            readable = re.sub(re.escape(original), placeholder, readable, flags=re.IGNORECASE)

        # Run anonymizer on whatever remains for any additional entities
        detection = self._detect(readable, settings, language)
        remaining = detection.replacements

        for original, placeholder in sorted(
            remaining.items(), key=lambda x: len(x[0]), reverse=True
        ):
            readable = readable.replace(original, placeholder)

        # Restore separator style (spaces → underscores in the new stem)
        return readable.replace(" ", "_"), remaining

    def rename_file(self, path: Path, settings: ProcessingSettings) -> FileResult:
        """Rename a single file's name in place using the same detection as content mode.

        File content is never opened or modified — only path.name changes.
        Used by the 'Rename names only' action, which anonymizes every path in
        a tree before an AI agent enumerates it (see FolderProcessor.rename_in_place).
        """
        self._language_detector.ensure_loaded(settings.language, settings.loading_strategy)
        new_stem, replacements = self._anonymize_stem(path.stem, {}, settings, settings.language)
        new_name = new_stem + path.suffix
        if new_name == path.name:
            return FileResult(status="clean", source_path=path, output_path=path)

        new_path = path.parent / new_name
        try:
            path.rename(new_path)
        except OSError as exc:
            logger.error("Failed to rename %s: %s", path, exc)
            return FileResult(status="error", source_path=path, error_message=str(exc))

        return FileResult(
            status="anonymized" if replacements else "clean",
            source_path=path,
            output_path=new_path,
            entities_found=len(replacements),
            replacements=replacements,
        )

    # ------------------------------------------------------------------
    # AI Mode extraction (text out, nothing written to disk)
    # ------------------------------------------------------------------

    def extract_anonymized_text(self, path: Path, settings: ProcessingSettings) -> ExtractResult:
        """Extract a file's text and return it anonymized, without writing anything to disk.

        Used by AI Mode's /ai/extract — reuses the same load/detect logic as
        Document Mode but stops short of writing an output file. The source
        file on disk is never modified.
        """
        ext = path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            return ExtractResult(
                status="skipped", source_path=path,
                error_message=f"Unsupported file type: {path.suffix}",
            )

        try:
            self._language_detector.ensure_loaded(settings.language, settings.loading_strategy)
            if ext == ".xlsx":
                return self._extract_xlsx(path, settings)
            if ext == ".pdf":
                return self._extract_pdf(path, settings)
            text = self._doc_processor.load_docx(path)[0] if ext == ".docx" else self._doc_processor.load_md(path)
            return self._extract_plain_text(path, text, settings)
        except Exception as exc:
            logger.error("Failed to extract %s: %s", path, exc)
            return ExtractResult(status="error", source_path=path, error_message=str(exc))

    def _extract_plain_text(self, path: Path, text: str, settings: ProcessingSettings) -> ExtractResult:
        """Shared extraction path for DOCX and Markdown, which reduce to a single text blob."""
        if not text.strip():
            return ExtractResult(status="clean", source_path=path, anonymized_text=text)

        detection = self._detect(text, settings, settings.language)
        if not detection.entities:
            return ExtractResult(status="clean", source_path=path, anonymized_text=text)

        anonymized_text = self._doc_processor.apply_replacements(text, detection.replacements)
        return ExtractResult(
            status="extracted", source_path=path, anonymized_text=anonymized_text,
            entities=detection.entities, replacements=detection.replacements,
        )

    def _extract_pdf(self, path: Path, settings: ProcessingSettings) -> ExtractResult:
        """Extract PDF text, flagging any page with no extractable text layer.

        pymupdf does not OCR — an image-only page yields empty text and is
        reported as a warning rather than silently passed through unanonymized.
        """
        text, doc = self._doc_processor.load_pdf(path)
        warnings: list[str] = []
        for index, page in enumerate(doc, start=1):
            if not page.get_text().strip():
                warnings.append(f"Page {index} has no extractable text (may be image-only) — review manually.")
        doc.close()

        if not text.strip():
            return ExtractResult(
                status="unreadable", source_path=path, warnings=warnings,
                error_message="PDF could not be read — may be image-based or have non-standard encoding.",
            )

        detection = self._detect(text, settings, settings.language)
        if not detection.entities:
            return ExtractResult(status="clean", source_path=path, anonymized_text=text, warnings=warnings)

        anonymized_text = self._doc_processor.apply_replacements(text, detection.replacements)
        return ExtractResult(
            status="extracted", source_path=path, anonymized_text=anonymized_text,
            entities=detection.entities, replacements=detection.replacements, warnings=warnings,
        )

    def _extract_xlsx(self, path: Path, settings: ProcessingSettings) -> ExtractResult:
        """Extract Excel text (row-concatenated string cells) with the same two-pass logic as Document Mode."""
        text, wb = self._doc_processor.load_xlsx(path)
        encoder = HashEncoder(settings.secret) if settings.hashing_enabled else None

        exact_replacements: dict[str, str] = {}
        if settings.excel_column_names:
            exact_replacements, _missing = self._doc_processor.extract_column_replacements(
                wb, settings.excel_column_names, encoder=encoder
            )

        entities: list[DetectedEntity] = []
        substring_replacements: dict[str, str] = {}
        if settings.excel_generic_enabled and text.strip():
            detection = self._detect(text, settings, settings.language)
            substring_replacements = detection.replacements
            entities = detection.entities

        combined = {**substring_replacements, **exact_replacements}
        if not combined:
            return ExtractResult(status="clean", source_path=path, anonymized_text=text)

        anonymized_text = self._doc_processor.apply_replacements(text, combined)
        return ExtractResult(
            status="extracted", source_path=path, anonymized_text=anonymized_text,
            entities=entities, replacements=combined,
        )

    # ------------------------------------------------------------------
    # Restore
    # ------------------------------------------------------------------

    _RESTORABLE_EXTENSIONS: frozenset[str] = frozenset({".docx", ".txt", ".md", ".xlsx"})

    def restore_file(self, input_path: Path, keyref_path: Path) -> FileResult:
        """Restore an anonymized file using a KEYREF CSV.

        Reads {placeholder: original} from keyref_path and replaces all
        occurrences in input_path, writing output to RESTORED_{filename}
        in the same directory. Returns replacement count in entities_found.
        """
        ext = input_path.suffix.lower()
        if ext not in self._RESTORABLE_EXTENSIONS:
            return FileResult(
                status="error",
                source_path=input_path,
                error_message=(
                    f"Unsupported file type for restore: {input_path.suffix}. "
                    "Supported: DOCX, XLSX, MD, TXT."
                ),
            )

        try:
            replacements = self._doc_processor.load_keyref_csv(keyref_path)
        except Exception as exc:
            logger.error("Failed to read KEYREF %s: %s", keyref_path, exc)
            return FileResult(
                status="error",
                source_path=input_path,
                error_message=f"Could not read KEYREF file: {exc}",
            )

        if not replacements:
            return FileResult(
                status="error",
                source_path=input_path,
                error_message="KEYREF file contained no placeholder mappings.",
            )

        # Apply replacements to the filename stem so any placeholders in the
        # anonymized filename are also resolved (e.g. ANON_[PERSON_1]_report.docx
        # → RESTORED_Craig_Bradley_report.docx).
        restored_stem = input_path.stem
        for placeholder, original in sorted(
            replacements.items(), key=lambda x: len(x[0]), reverse=True
        ):
            if placeholder in restored_stem:
                restored_stem = restored_stem.replace(placeholder, original)
        output_path = input_path.parent / f"RESTORED_{restored_stem}{input_path.suffix}"

        try:
            if ext == ".docx":
                count = self._doc_processor.restore_docx(input_path, output_path, replacements)
            elif ext == ".xlsx":
                count = self._doc_processor.restore_xlsx(input_path, output_path, replacements)
            else:
                count = self._doc_processor.restore_text(input_path, output_path, replacements)
        except Exception as exc:
            logger.error("Restore failed for %s: %s", input_path, exc)
            return FileResult(
                status="error",
                source_path=input_path,
                error_message=str(exc),
            )

        return FileResult(
            status="restored",
            source_path=input_path,
            output_path=output_path,
            entities_found=count,
        )

    def _write_keyref(
        self,
        keyref_path: Path,
        source_path: Path,
        replacements: dict[str, str],
        entities: list[DetectedEntity],
        exact_replacements: Optional[dict[str, str]] = None,
    ) -> None:
        """Write a human-readable key reference file mapping placeholders to originals."""
        sep = "─" * 60
        lines = [
            "d-tach Key Reference",
            f"Source : {source_path.name}",
            f"Date   : {date.today().isoformat()}",
            sep,
            f"{'PLACEHOLDER':<30} {'ORIGINAL VALUE':<25} TYPE",
            sep,
        ]

        seen: set[str] = set()
        for entity in entities:
            placeholder = replacements.get(entity.original_text, entity.placeholder)
            if placeholder in seen:
                continue
            seen.add(placeholder)
            lines.append(
                f"{placeholder:<30} {entity.original_text:<25} {entity.entity_type}"
            )

        if exact_replacements:
            for original, placeholder in exact_replacements.items():
                if placeholder in seen:
                    continue
                seen.add(placeholder)
                label = placeholder.strip("[]").rsplit("_", 1)[0]
                lines.append(f"{placeholder:<30} {original:<25} {label}")

        lines.append(sep)
        keyref_path.write_text("\n".join(lines), encoding="utf-8")
