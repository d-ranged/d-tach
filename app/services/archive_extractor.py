"""Expand compressed archives in place before a folder is processed.

A folder that still contains zipped subfolders is not ready to be looked at:
the archive's own name gets anonymized, but nothing inside it does, and an
agent enumerating the tree has no way to know what it is not seeing. Expanding
archives first means the tree on disk is the whole tree.

Extraction is deliberately conservative — it refuses members that would land
outside the destination, caps how far it will follow archives nested inside
archives, and never deletes the original unless asked to.
"""
import logging
import tarfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Generator, Optional

logger = logging.getLogger(__name__)

ZIP_EXTENSIONS = frozenset({".zip"})
TAR_EXTENSIONS = frozenset({".tar", ".tgz", ".tbz2", ".txz"})
# Compound suffixes handled separately since Path.suffix only sees the last part.
TAR_COMPOUND_SUFFIXES = (".tar.gz", ".tar.bz2", ".tar.xz")

ARCHIVE_EXTENSIONS = ZIP_EXTENSIONS | TAR_EXTENSIONS

MAX_NESTING_DEPTH = 5


def is_archive(path: Path) -> bool:
    """Return True if path looks like an archive this module can expand."""
    name = path.name.lower()
    if any(name.endswith(suffix) for suffix in TAR_COMPOUND_SUFFIXES):
        return True
    return path.suffix.lower() in ARCHIVE_EXTENSIONS


def _archive_stem(path: Path) -> str:
    """Return the archive's name without its extension, compound suffixes included."""
    name = path.name
    lowered = name.lower()
    for suffix in TAR_COMPOUND_SUFFIXES:
        if lowered.endswith(suffix):
            return name[: -len(suffix)]
    return path.stem


@dataclass
class ArchiveResult:
    """The outcome of expanding a single archive."""

    status: str  # "expanded" | "error" | "skipped"
    source_path: Path
    destination: Optional[Path] = None
    member_count: int = 0
    error_message: str = ""
    deleted_source: bool = False


class ArchiveExtractor:
    """Recursively expands archives found under a folder."""

    def __init__(self, max_depth: int = MAX_NESTING_DEPTH) -> None:
        """Initialise with a cap on how deep nested archives are followed."""
        self._max_depth = max_depth

    def expand_all(
        self, folder: Path, delete_after: bool = False
    ) -> Generator[ArchiveResult, None, None]:
        """Expand every archive under folder, including archives inside archives.

        Yields one ArchiveResult per archive as it completes. Each pass rescans
        the tree, so an archive that only appeared because a parent archive was
        expanded is picked up on the next pass, up to max_depth passes.

        delete_after removes an archive once it has been expanded successfully.
        Off by default — expanding is reversible, deleting is not.
        """
        seen: set[Path] = set()

        for _ in range(self._max_depth):
            pending = [
                p for p in sorted(folder.rglob("*"))
                if p.is_file() and is_archive(p) and p.resolve() not in seen
            ]
            if not pending:
                return

            for archive in pending:
                seen.add(archive.resolve())
                result = self.expand_one(archive, delete_after=delete_after)
                yield result

    def expand_one(self, archive: Path, delete_after: bool = False) -> ArchiveResult:
        """Expand a single archive into a new sibling folder named after it."""
        try:
            destination = self._unique_destination(archive)
            if zipfile.is_zipfile(archive):
                member_count = self._extract_zip(archive, destination)
            elif tarfile.is_tarfile(archive):
                member_count = self._extract_tar(archive, destination)
            else:
                return ArchiveResult(
                    status="skipped",
                    source_path=archive,
                    error_message="Not a readable zip or tar archive.",
                )
        except Exception as exc:  # noqa: BLE001 - one bad archive must not stop the run
            logger.error("Failed to expand %s: %s", archive, exc)
            return ArchiveResult(status="error", source_path=archive, error_message=str(exc))

        deleted = False
        if delete_after:
            try:
                archive.unlink()
                deleted = True
            except OSError as exc:
                logger.warning("Expanded %s but could not delete it: %s", archive, exc)

        return ArchiveResult(
            status="expanded",
            source_path=archive,
            destination=destination,
            member_count=member_count,
            deleted_source=deleted,
        )

    @staticmethod
    def _unique_destination(archive: Path) -> Path:
        """Return a folder path beside the archive that does not already exist."""
        base = archive.parent / _archive_stem(archive)
        if not base.exists():
            return base
        for n in range(2, 100):
            candidate = archive.parent / f"{_archive_stem(archive)}_{n}"
            if not candidate.exists():
                return candidate
        raise OSError(f"Could not find a free destination folder for {archive.name}")

    @staticmethod
    def _is_within(destination: Path, target: Path) -> bool:
        """Return True if target resolves to somewhere inside destination."""
        try:
            target.resolve().relative_to(destination.resolve())
        except ValueError:
            return False
        return True

    def _extract_zip(self, archive: Path, destination: Path) -> int:
        """Extract a zip, refusing any member that would escape destination."""
        destination.mkdir(parents=True, exist_ok=True)
        count = 0
        with zipfile.ZipFile(archive) as zf:
            for member in zf.infolist():
                target = destination / member.filename
                if not self._is_within(destination, target):
                    raise ValueError(
                        f"Archive member would extract outside the destination: {member.filename}"
                    )
                zf.extract(member, destination)
                if not member.is_dir():
                    count += 1
        return count

    def _extract_tar(self, archive: Path, destination: Path) -> int:
        """Extract a tar using the 'data' filter where the runtime provides it."""
        destination.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as tf:
            members = tf.getmembers()
            for member in members:
                target = destination / member.name
                if not self._is_within(destination, target):
                    raise ValueError(
                        f"Archive member would extract outside the destination: {member.name}"
                    )
            try:
                # Python 3.12+ (and 3.11.4+) reject unsafe members outright.
                tf.extractall(destination, filter="data")
            except TypeError:
                tf.extractall(destination)
        return sum(1 for m in members if m.isfile())
