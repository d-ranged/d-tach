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
    NUMERIC_ID_ENTITY,
    build_numeric_id_recognizer,
)
from app.services.document_processor import DocumentProcessor
from app.services.hash_encoder import HashEncoder
from app.services.language_detector import LanguageDetector
from app.services.pattern_config import PatternConfig

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pdf", ".md"})

# Entities whose matched text is shorter than this are almost certainly PDF
# ligature extraction artefacts (e.g. "ci", "fi") rather than real PII.
# Replacing them would corrupt the entire document, so they are skipped.
MIN_ENTITY_TEXT_LENGTH: int = 3


def _build_entity_list(anonymize_dates: bool, numeric_id_enabled: bool = False) -> list[str]:
    """Return the entity list to pass to the Anonymizer.

    DATE_TIME is excluded unless the user has opted in, as dates are
    ubiquitous in academic documents and rarely personally identifying.
    NUMERIC_ID is included only when numeric ID detection is enabled.
    """
    from app.services.anonymizer import ENTITIES
    result = list(ENTITIES) if anonymize_dates else [e for e in ENTITIES if e != "DATE_TIME"]
    if numeric_id_enabled:
        result.append(NUMERIC_ID_ENTITY)
    return result


@dataclass
class ProcessingSettings:
    """Configuration for a single file processing run."""

    hashing_enabled: bool = False
    secret: str = ""
    key_reference_enabled: bool = False
    check_file_names: bool = False
    language: str = "en"
    anonymize_dates: bool = False
    numeric_id_enabled: bool = False
    digit_count: int = 7


@dataclass
class FileResult:
    """The outcome of processing a single file."""

    status: str  # "anonymized" | "clean" | "error" | "skipped"
    source_path: Path
    output_path: Optional[Path] = None
    keyref_path: Optional[Path] = None
    entities_found: int = 0
    error_message: Optional[str] = None


class FileProcessor:
    """Processes a single supported file: detects PII, writes anonymized output.

    Output files are written to the same directory as the source:
    - PII detected  → ANON_{original_name}
    - No PII found  → CHECKED_{original_name}
    - Key reference → KEYREF_{original_stem}.txt  (when enabled)
    """

    def __init__(
        self, anonymizer: Anonymizer, language_detector: LanguageDetector
    ) -> None:
        """Initialise with shared service instances."""
        self._anonymizer = anonymizer
        self._language_detector = language_detector
        self._doc_processor = DocumentProcessor()

    def process(self, path: Path, settings: ProcessingSettings) -> FileResult:
        """Process a single file and return a FileResult describing the outcome.

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
            if ext == ".docx":
                return self._process_docx(path, settings)
            if ext == ".md":
                return self._process_markdown(path, settings)
            return self._process_pdf(path, settings)
        except Exception as exc:
            logger.error("Failed to process %s: %s", path, exc)
            return FileResult(
                status="error",
                source_path=path,
                error_message=str(exc),
            )

    # ------------------------------------------------------------------
    # Internal processing
    # ------------------------------------------------------------------

    def _process_docx(self, path: Path, settings: ProcessingSettings) -> FileResult:
        """Core DOCX processing logic."""
        text, doc = self._doc_processor.load_docx(path)

        if not text.strip():
            output_name = f"CHECKED_{path.name}"
            if settings.check_file_names:
                output_name = self._anonymize_filename(
                    f"CHECKED_{path.stem}", path.suffix, {}, settings, settings.language
                )
            output_path = path.parent / output_name
            self._doc_processor.save_docx_copy(doc, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        language = settings.language
        entities = _build_entity_list(settings.anonymize_dates, settings.numeric_id_enabled)
        ad_hoc = self._build_ad_hoc_recognizers(settings, language)
        result = self._anonymizer.anonymize(text, language, entities=entities, ad_hoc_recognizers=ad_hoc)

        if not result.entities:
            output_name = f"CHECKED_{path.name}"
            if settings.check_file_names:
                output_name = self._anonymize_filename(
                    f"CHECKED_{path.stem}", path.suffix, {}, settings, language
                )
            output_path = path.parent / output_name
            self._doc_processor.save_docx_copy(doc, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        # Build replacement map: original text → placeholder (with optional hashing)
        encoder = HashEncoder(settings.secret) if settings.hashing_enabled else None
        replacements = self._build_replacements(result.entities, encoder)

        output_name = f"ANON_{path.name}"
        if settings.check_file_names:
            output_name = self._anonymize_filename(
                f"ANON_{path.stem}", path.suffix, replacements, settings, language
            )

        output_path = path.parent / output_name
        self._doc_processor.save_docx_with_replacements(doc, output_path, replacements)

        keyref_path: Optional[Path] = None
        if settings.key_reference_enabled:
            keyref_path = path.parent / f"KEYREF_{path.stem}.txt"
            self._write_keyref(keyref_path, path, replacements, result.entities)

        return FileResult(
            status="anonymized",
            source_path=path,
            output_path=output_path,
            keyref_path=keyref_path,
            entities_found=len({e.original_text for e in result.entities}),
        )

    def _process_pdf(self, path: Path, settings: ProcessingSettings) -> FileResult:
        """Core PDF processing logic using pymupdf in-place redaction."""
        import fitz  # local import — only needed for PDF path

        text, doc = self._doc_processor.load_pdf(path)

        if not text.strip():
            output_name = f"CHECKED_{path.name}"
            if settings.check_file_names:
                output_name = self._anonymize_filename(
                    f"CHECKED_{path.stem}", path.suffix, {}, settings, settings.language
                )
            doc.close()
            output_path = path.parent / output_name
            clean_doc = fitz.open(str(path))
            self._doc_processor.save_pdf_copy(clean_doc, output_path)
            clean_doc.close()
            return FileResult(status="clean", source_path=path, output_path=output_path)

        language = settings.language
        entities = _build_entity_list(settings.anonymize_dates, settings.numeric_id_enabled)
        ad_hoc = self._build_ad_hoc_recognizers(settings, language)
        result = self._anonymizer.anonymize(text, language, entities=entities, ad_hoc_recognizers=ad_hoc)

        if not result.entities:
            output_name = f"CHECKED_{path.name}"
            if settings.check_file_names:
                output_name = self._anonymize_filename(
                    f"CHECKED_{path.stem}", path.suffix, {}, settings, language
                )
            doc.close()
            output_path = path.parent / output_name
            clean_doc = fitz.open(str(path))
            self._doc_processor.save_pdf_copy(clean_doc, output_path)
            clean_doc.close()
            return FileResult(status="clean", source_path=path, output_path=output_path)

        encoder = HashEncoder(settings.secret) if settings.hashing_enabled else None
        replacements = self._build_replacements(result.entities, encoder)

        output_name = f"ANON_{path.name}"
        if settings.check_file_names:
            output_name = self._anonymize_filename(
                f"ANON_{path.stem}", path.suffix, replacements, settings, language
            )

        output_path = path.parent / output_name
        self._doc_processor.save_pdf_with_replacements(doc, output_path, replacements)
        doc.close()

        keyref_path: Optional[Path] = None
        if settings.key_reference_enabled:
            keyref_path = path.parent / f"KEYREF_{path.stem}.txt"
            self._write_keyref(keyref_path, path, replacements, result.entities)

        return FileResult(
            status="anonymized",
            source_path=path,
            output_path=output_path,
            keyref_path=keyref_path,
            entities_found=len({e.original_text for e in result.entities}),
        )

    def _process_markdown(self, path: Path, settings: ProcessingSettings) -> FileResult:
        """Core Markdown processing logic.

        Markdown files are treated as plain text: the full content is fed to
        the anonymizer and replacements are written back with str.replace().
        Markdown syntax is preserved because PII replacements only touch the
        matched text spans, not surrounding formatting characters.
        """
        text = self._doc_processor.load_md(path)

        if not text.strip():
            output_name = f"CHECKED_{path.name}"
            if settings.check_file_names:
                output_name = self._anonymize_filename(
                    f"CHECKED_{path.stem}", path.suffix, {}, settings, settings.language
                )
            output_path = path.parent / output_name
            self._doc_processor.save_md_copy(text, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        language = settings.language
        entities = _build_entity_list(settings.anonymize_dates, settings.numeric_id_enabled)
        ad_hoc = self._build_ad_hoc_recognizers(settings, language)
        result = self._anonymizer.anonymize(text, language, entities=entities, ad_hoc_recognizers=ad_hoc)

        if not result.entities:
            output_name = f"CHECKED_{path.name}"
            if settings.check_file_names:
                output_name = self._anonymize_filename(
                    f"CHECKED_{path.stem}", path.suffix, {}, settings, language
                )
            output_path = path.parent / output_name
            self._doc_processor.save_md_copy(text, output_path)
            return FileResult(status="clean", source_path=path, output_path=output_path)

        encoder = HashEncoder(settings.secret) if settings.hashing_enabled else None
        replacements = self._build_replacements(result.entities, encoder)

        output_name = f"ANON_{path.name}"
        if settings.check_file_names:
            output_name = self._anonymize_filename(
                f"ANON_{path.stem}", path.suffix, replacements, settings, language
            )

        output_path = path.parent / output_name
        self._doc_processor.save_md_with_replacements(text, output_path, replacements)

        keyref_path: Optional[Path] = None
        if settings.key_reference_enabled:
            keyref_path = path.parent / f"KEYREF_{path.stem}.txt"
            self._write_keyref(keyref_path, path, replacements, result.entities)

        return FileResult(
            status="anonymized",
            source_path=path,
            output_path=output_path,
            keyref_path=keyref_path,
            entities_found=len({e.original_text for e in result.entities}),
        )

    def _build_ad_hoc_recognizers(
        self, settings: ProcessingSettings, language: str
    ) -> list:
        """Return a list of ad-hoc recognizers for this processing run.

        Includes a NumericIdRecognizer when numeric ID detection is enabled.
        """
        if not settings.numeric_id_enabled:
            return []
        config = PatternConfig(digit_count=settings.digit_count)
        return [build_numeric_id_recognizer(config, language)]

    def _build_replacements(
        self,
        entities: list[DetectedEntity],
        encoder: Optional[HashEncoder],
    ) -> dict[str, str]:
        """Return a mapping of original text → replacement placeholder.

        When hashing is enabled, PERSON entities are replaced with hash-encoded
        names. All other entity types use the sequential placeholder produced
        by the Anonymizer.
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
            else:
                replacements[entity.original_text] = entity.placeholder
        return replacements

    def _anonymize_filename(
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

        Case-insensitive matching is necessary because filenames often use
        different capitalisation than the text in the document body (e.g.
        'nick_surname' in a filename vs 'Nick Surname' detected in the text).
        The replacement placeholder is always written in its original form
        (uppercase entity type + counter, or hash-encoded for PERSON).
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
        ad_hoc = self._build_ad_hoc_recognizers(settings, language)
        anon_result = self._anonymizer.anonymize(
            readable, language,
            entities=_build_entity_list(settings.anonymize_dates, settings.numeric_id_enabled),
            ad_hoc_recognizers=ad_hoc,
        )
        encoder = HashEncoder(settings.secret) if settings.hashing_enabled else None
        remaining = self._build_replacements(anon_result.entities, encoder)

        for original, placeholder in sorted(
            remaining.items(), key=lambda x: len(x[0]), reverse=True
        ):
            readable = readable.replace(original, placeholder)

        # Restore separator style (spaces → underscores in the new stem)
        new_stem = readable.replace(" ", "_")
        return new_stem + suffix

    def _write_keyref(
        self,
        keyref_path: Path,
        source_path: Path,
        replacements: dict[str, str],
        entities: list[DetectedEntity],
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

        lines.append(sep)
        keyref_path.write_text("\n".join(lines), encoding="utf-8")
