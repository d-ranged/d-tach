import csv
import logging
from dataclasses import dataclass, field, replace as dc_replace
from pathlib import Path
from typing import Generator, Optional

from app.services.file_processor import FileProcessor, FileResult, ProcessingSettings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pdf", ".md", ".xlsx"})


@dataclass
class FolderSummary:
    """Aggregate result of processing all files in a folder."""

    total: int = 0
    anonymized: int = 0
    clean: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[FileResult] = field(default_factory=list)
    keyref_csv_path: Optional[Path] = None


class FolderProcessor:
    """Recursively processes all supported files in a folder.

    Files are processed deepest-first (via rglob). Folder renaming is not
    implemented in this step — that requires tracking every output path and
    renaming directories after all content is processed, which is Step 9+.

    Progress is reported by yielding each FileResult as it completes so the
    caller can stream updates to the UI.
    """

    def __init__(self, file_processor: FileProcessor) -> None:
        """Initialise with a shared FileProcessor instance."""
        self._file_processor = file_processor

    def collect_files(self, folder: Path) -> list[Path]:
        """Return all supported files under folder, sorted deepest-first.

        Deepest-first ensures subfolders are fully processed before their
        parent, which matters when folder renaming is added later.
        """
        files = [
            p for p in folder.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        # Sort by depth (number of parts) descending, then alphabetically
        return sorted(files, key=lambda p: (-len(p.parts), str(p)))

    def process(
        self, folder: Path, settings: ProcessingSettings
    ) -> Generator[tuple[FileResult, int, int], None, None]:
        """Process all supported files in folder, yielding progress after each file.

        Yields a tuple of (FileResult, current_index, total_count) for each file.
        Errors on individual files are caught and yielded as error FileResults so
        processing continues with remaining files.

        Usage::

            for result, n, total in processor.process(folder, settings):
                # stream result to UI
        """
        files = self.collect_files(folder)
        total = len(files)

        # Suppress per-file keyrefs in folder mode — a consolidated CSV is written
        # by summarise() instead, so individual .txt files don't litter the folder.
        file_settings = (
            dc_replace(settings, key_reference_enabled=False)
            if settings.key_reference_enabled
            else settings
        )

        for index, path in enumerate(files, start=1):
            try:
                result = self._file_processor.process(path, file_settings)
            except Exception as exc:
                logger.error("Unexpected error processing %s: %s", path, exc)
                result = FileResult(
                    status="error",
                    source_path=path,
                    error_message=str(exc),
                )
            yield result, index, total

    def summarise(
        self,
        results: list[FileResult],
        folder: Optional[Path] = None,
        key_reference_enabled: bool = False,
    ) -> FolderSummary:
        """Build a FolderSummary from a completed list of FileResults.

        When key_reference_enabled is True and folder is provided, writes a
        consolidated KEYREF_<folder>.csv at the folder root aggregating all
        replacements from every anonymized file in the run.
        """
        summary = FolderSummary(total=len(results), results=results)
        for r in results:
            if r.status == "anonymized":
                summary.anonymized += 1
            elif r.status == "clean":
                summary.clean += 1
            elif r.status == "skipped":
                summary.skipped += 1
            else:
                summary.errors += 1

        if key_reference_enabled and folder:
            summary.keyref_csv_path = self._write_consolidated_keyref(results, folder)

        return summary

    def _write_consolidated_keyref(
        self, results: list[FileResult], folder: Path
    ) -> Optional[Path]:
        """Write a two-column CSV mapping all placeholders to original values.

        Aggregates replacements from every anonymized file. Duplicate
        (placeholder, original) pairs are written once. Returns None when no
        replacements were found across all files.
        """
        seen: set[tuple[str, str]] = set()
        rows: list[tuple[str, str]] = []

        for result in results:
            for original, placeholder in result.replacements.items():
                pair = (placeholder, original)
                if pair not in seen:
                    seen.add(pair)
                    rows.append(pair)

        if not rows:
            return None

        rows.sort()
        csv_path = folder / f"KEYREF_{folder.name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Placeholder", "Original value"])
            writer.writerows(rows)

        return csv_path
