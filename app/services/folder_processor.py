import csv
import logging
import shutil
from dataclasses import dataclass, field, replace as dc_replace
from pathlib import Path
from typing import Generator, Optional

from app.services.file_processor import (
    FileProcessor,
    FileResult,
    PlaceholderLedger,
    ProcessingSettings,
)
from app.services.archive_extractor import ArchiveExtractor, ArchiveResult

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({".docx", ".pdf", ".md", ".xlsx"})


def normalize_extensions(raw: str) -> list[str]:
    """Parse a comma-separated extension list into normalized lowercase forms.

    Accepts entries with or without a leading dot (e.g. "sql" or ".sql");
    both are stored as ".sql". Blank entries are dropped. Empty input
    returns an empty list.
    """
    extensions: list[str] = []
    for part in raw.split(","):
        ext = part.strip().lower()
        if not ext:
            continue
        if not ext.startswith("."):
            ext = f".{ext}"
        extensions.append(ext)
    return extensions


@dataclass
class FolderSummary:
    """Aggregate result of processing all files in a folder."""

    total: int = 0
    anonymized: int = 0
    clean: int = 0
    unreadable: int = 0
    skipped: int = 0
    errors: int = 0
    copied: int = 0
    results: list[FileResult] = field(default_factory=list)
    keyref_csv_path: Optional[Path] = None


class FolderProcessor:
    """Recursively processes all supported files in a folder.

    Files are processed deepest-first (via rglob). When check_file_names is
    enabled and output_mode is subfolder, folder names inside the anonymized/
    output directory are renamed after all file content is complete, deepest
    first so that renaming a parent never invalidates a child's path.

    Progress is reported by yielding each FileResult as it completes so the
    caller can stream updates to the UI.
    """

    def __init__(self, file_processor: FileProcessor) -> None:
        """Initialise with a shared FileProcessor instance."""
        self._file_processor = file_processor

    def collect_files(
        self, folder: Path, pass_through_extensions: frozenset[str] = frozenset()
    ) -> list[Path]:
        """Return all supported and pass-through files under folder, sorted deepest-first.

        Deepest-first ensures subfolders are fully processed before their
        parent, which matters when folder renaming is added later.

        pass_through_extensions are file types copied verbatim without PII
        scanning (e.g. .sql, .py) — opt-in, empty by default.

        The anonymized/ subfolder (created in subfolder output mode) is always
        excluded so re-running on the same folder does not re-process output.
        """
        anonymized_root = folder / "anonymized"
        allowed = SUPPORTED_EXTENSIONS | pass_through_extensions
        files = [
            p for p in folder.rglob("*")
            if p.is_file()
            and p.suffix.lower() in allowed
            and anonymized_root not in p.parents
        ]
        # Sort by depth (number of parts) descending, then alphabetically
        return sorted(files, key=lambda p: (-len(p.parts), str(p)))

    @staticmethod
    def _subfolder_output_path(path: Path, chosen_folder: Path) -> Path:
        """Compute the mirror output path inside chosen_folder/anonymized/.

        Example: chosen/sub/file.docx → chosen/anonymized/sub/file.docx
        """
        relative = path.relative_to(chosen_folder)
        return chosen_folder / "anonymized" / relative

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
        pass_through_extensions = frozenset(
            e.lower() for e in settings.pass_through_extensions
        )
        files = self.collect_files(folder, pass_through_extensions)
        total = len(files)

        # Suppress per-file keyrefs in folder mode — a consolidated CSV is written
        # by summarise() instead, so individual .txt files don't litter the folder.
        file_settings = (
            dc_replace(settings, key_reference_enabled=False)
            if settings.key_reference_enabled
            else settings
        )
        file_settings = self._with_shared_numbering(file_settings)

        completed: list[FileResult] = []
        for index, path in enumerate(files, start=1):
            if path.suffix.lower() in pass_through_extensions and path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                result = self._copy_pass_through(path, folder)
                completed.append(result)
                yield result, index, total
                continue

            output_path_override = None
            if settings.output_mode == "subfolder":
                output_path_override = self._subfolder_output_path(path, folder)
                output_path_override.parent.mkdir(parents=True, exist_ok=True)

            try:
                result = self._file_processor.process(path, file_settings, output_path_override)
            except Exception as exc:
                logger.error("Unexpected error processing %s: %s", path, exc)
                result = FileResult(
                    status="error",
                    source_path=path,
                    error_message=str(exc),
                )
            completed.append(result)
            yield result, index, total

        if settings.check_file_names:
            anonymized_root = folder / "anonymized"
            if anonymized_root.exists():
                all_replacements: dict[str, str] = {}
                for r in completed:
                    all_replacements.update(r.replacements)
                self._rename_output_folders(anonymized_root, all_replacements, settings)

    def expand_archives(
        self, folder: Path, settings: ProcessingSettings
    ) -> Generator[ArchiveResult, None, None]:
        """Expand zip/tar archives under folder so the tree on disk is the whole tree.

        A no-op unless settings.expand_archives is on. Runs before any renaming
        so that files which only exist inside an archive are named, counted and
        enumerable like everything else.

        Usage mirrors process()::

            for result in processor.expand_archives(folder, settings):
                # stream result to UI
        """
        if not settings.expand_archives:
            return
        extractor = ArchiveExtractor()
        yield from extractor.expand_all(
            folder, delete_after=settings.delete_archives_after_expand
        )

    def rename_in_place(
        self, folder: Path, settings: ProcessingSettings
    ) -> Generator[tuple[FileResult, int, int], None, None]:
        """Rename every file and folder name under folder in place, deepest-first.

        No file content is read or rewritten and no anonymized/ output tree is
        created — only names change. This is the 'Rename names only' action: a
        prerequisite for pointing AI Mode at a real folder, since without it an
        agent enumerating the tree would see real names in the paths. Every file
        is included regardless of extension, since the goal is safe path
        enumeration rather than content anonymization.

        Usage mirrors process()::

            for result, n, total in processor.rename_in_place(folder, settings):
                # stream result to UI
        """
        settings = self._with_shared_numbering(settings)
        files = self._collect_all_files(folder)
        total = len(files)
        all_replacements: dict[str, str] = {}

        for index, path in enumerate(files, start=1):
            try:
                result = self._file_processor.rename_file(path, settings)
            except Exception as exc:
                logger.error("Unexpected error renaming %s: %s", path, exc)
                result = FileResult(status="error", source_path=path, error_message=str(exc))
            all_replacements.update(result.replacements)
            yield result, index, total

        self._rename_directories_in_place(folder, all_replacements, settings)

    @staticmethod
    def _with_shared_numbering(settings: ProcessingSettings) -> ProcessingSettings:
        """Return settings carrying one numbering for the whole folder run.

        Needed only with hashing off: sequential placeholders restart at 1 in
        every file, so without a shared ledger the consolidated KEYREF maps one
        placeholder to several people. With hashing on, the same value already
        encodes the same way everywhere.
        """
        if settings.hashing_enabled or settings.placeholder_ledger is not None:
            return settings
        return dc_replace(settings, placeholder_ledger=PlaceholderLedger())

    @staticmethod
    def _collect_all_files(folder: Path) -> list[Path]:
        """Return every file under folder (any extension), sorted deepest-first."""
        files = [p for p in folder.rglob("*") if p.is_file()]
        return sorted(files, key=lambda p: (-len(p.parts), str(p)))

    def _rename_directories_in_place(
        self, folder: Path, all_replacements: dict[str, str], settings: ProcessingSettings,
    ) -> None:
        """Rename every subdirectory of folder in place, deepest first. folder itself is untouched."""
        dirs = sorted(
            [p for p in folder.rglob("*") if p.is_dir()],
            key=lambda p: -len(p.parts),
        )
        for d in dirs:
            new_name = self._file_processor.anonymize_filename(
                d.name, "", all_replacements, settings, settings.language,
            )
            if new_name != d.name:
                d.rename(d.parent / new_name)

    def _copy_pass_through(self, path: Path, folder: Path) -> FileResult:
        """Copy a pass-through file verbatim to its mirrored anonymized/ path.

        No PII scanning or renaming is performed — original filename and
        content are preserved exactly. Used for non-scannable file types
        (e.g. .sql, .py, .mp4) opted into via PASS_THROUGH_EXTENSIONS.
        """
        output_path = self._subfolder_output_path(path, folder)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, output_path)
        except OSError as exc:
            logger.error("Failed to copy pass-through file %s: %s", path, exc)
            return FileResult(status="error", source_path=path, error_message=str(exc))
        return FileResult(status="copied", source_path=path, output_path=output_path)

    def _rename_output_folders(
        self,
        output_root: Path,
        all_replacements: dict[str, str],
        settings: ProcessingSettings,
    ) -> None:
        """Rename directories inside output_root whose names contain PII.

        Processes deepest directories first so that renaming a child directory
        does not invalidate the paths of its siblings, and renaming a parent
        does not invalidate the already-resolved paths of its children.
        Source directories are never touched — only directories inside
        output_root (i.e. the anonymized/ subfolder) are renamed.
        """
        dirs = sorted(
            [p for p in output_root.rglob("*") if p.is_dir()],
            key=lambda p: -len(p.parts),
        )
        for d in dirs:
            new_name = self._file_processor.anonymize_filename(
                d.name, "", all_replacements, settings, settings.language,
            )
            if new_name != d.name:
                d.rename(d.parent / new_name)

    def summarise(
        self,
        results: list[FileResult],
        folder: Optional[Path] = None,
        key_reference_enabled: bool = False,
        output_mode: str = "prefix",
    ) -> FolderSummary:
        """Build a FolderSummary from a completed list of FileResults.

        When key_reference_enabled is True and folder is provided, writes a
        consolidated KEYREF_<folder>.csv. In subfolder mode the CSV is placed
        inside folder/anonymized/; in prefix mode it goes at the folder root.
        """
        summary = FolderSummary(total=len(results), results=results)
        for r in results:
            if r.status == "anonymized":
                summary.anonymized += 1
            elif r.status == "clean":
                summary.clean += 1
            elif r.status == "unreadable":
                summary.unreadable += 1
            elif r.status == "skipped":
                summary.skipped += 1
            elif r.status == "copied":
                summary.copied += 1
            else:
                summary.errors += 1

        if key_reference_enabled and folder:
            if output_mode == "subfolder":
                csv_dir = folder / "anonymized"
                csv_dir.mkdir(exist_ok=True)
            else:
                csv_dir = folder
            summary.keyref_csv_path = self._write_consolidated_keyref(
                results, csv_dir, folder.name
            )

        return summary

    def _write_consolidated_keyref(
        self, results: list[FileResult], csv_dir: Path, folder_name: str
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
        csv_path = csv_dir / f"KEYREF_{folder_name}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Placeholder", "Original value"])
            writer.writerows(rows)

        return csv_path
