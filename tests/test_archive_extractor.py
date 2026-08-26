"""Tests for expanding archives found in a folder before it is processed."""

import tarfile
import zipfile
from pathlib import Path

import pytest

from app.services.archive_extractor import ArchiveExtractor, is_archive
from app.services.file_processor import ProcessingSettings
from app.services.folder_processor import FolderProcessor


def _make_zip(path: Path, entries: dict[str, str]) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        for name, content in entries.items():
            zf.writestr(name, content)
    return path


class TestIsArchive:
    @pytest.mark.parametrize(
        "name", ["a.zip", "a.tar", "a.tgz", "a.tar.gz", "a.tar.bz2", "a.TAR.GZ", "a.ZIP"]
    )
    def test_recognises_archives(self, name: str) -> None:
        assert is_archive(Path(name)) is True

    @pytest.mark.parametrize("name", ["a.docx", "a.pdf", "a.txt", "a.zipper", "a"])
    def test_rejects_non_archives(self, name: str) -> None:
        assert is_archive(Path(name)) is False


class TestExpandOne:
    def test_extracts_into_a_folder_named_after_the_archive(self, tmp_path: Path) -> None:
        _make_zip(tmp_path / "reports.zip", {"a.txt": "one", "sub/b.txt": "two"})

        result = ArchiveExtractor().expand_one(tmp_path / "reports.zip")

        assert result.status == "expanded"
        assert result.destination == tmp_path / "reports"
        assert result.member_count == 2
        assert (tmp_path / "reports" / "a.txt").read_text() == "one"
        assert (tmp_path / "reports" / "sub" / "b.txt").read_text() == "two"

    def test_keeps_the_archive_by_default(self, tmp_path: Path) -> None:
        _make_zip(tmp_path / "reports.zip", {"a.txt": "one"})

        result = ArchiveExtractor().expand_one(tmp_path / "reports.zip")

        assert (tmp_path / "reports.zip").exists()
        assert result.deleted_source is False

    def test_deletes_the_archive_when_asked(self, tmp_path: Path) -> None:
        _make_zip(tmp_path / "reports.zip", {"a.txt": "one"})

        result = ArchiveExtractor().expand_one(tmp_path / "reports.zip", delete_after=True)

        assert not (tmp_path / "reports.zip").exists()
        assert result.deleted_source is True

    def test_does_not_overwrite_an_existing_folder(self, tmp_path: Path) -> None:
        (tmp_path / "reports").mkdir()
        (tmp_path / "reports" / "existing.txt").write_text("keep me")
        _make_zip(tmp_path / "reports.zip", {"a.txt": "one"})

        result = ArchiveExtractor().expand_one(tmp_path / "reports.zip")

        assert result.destination == tmp_path / "reports_2"
        assert (tmp_path / "reports" / "existing.txt").read_text() == "keep me"

    def test_compound_suffix_strips_the_whole_extension(self, tmp_path: Path) -> None:
        inner = tmp_path / "payload.txt"
        inner.write_text("data")
        with tarfile.open(tmp_path / "bundle.tar.gz", "w:gz") as tf:
            tf.add(inner, arcname="payload.txt")
        inner.unlink()

        result = ArchiveExtractor().expand_one(tmp_path / "bundle.tar.gz")

        assert result.destination == tmp_path / "bundle"
        assert (tmp_path / "bundle" / "payload.txt").read_text() == "data"

    def test_a_corrupt_archive_reports_an_error_rather_than_raising(self, tmp_path: Path) -> None:
        broken = tmp_path / "broken.zip"
        broken.write_bytes(b"this is not a zip file")

        result = ArchiveExtractor().expand_one(broken)

        assert result.status == "skipped"


class TestPathTraversalIsRefused:
    """An archive must never write outside the folder it is being expanded into."""

    def test_parent_relative_member_is_refused(self, tmp_path: Path) -> None:
        target = tmp_path / "victim.txt"
        archive = tmp_path / "evil.zip"
        with zipfile.ZipFile(archive, "w") as zf:
            zf.writestr("../victim.txt", "owned")

        result = ArchiveExtractor().expand_one(archive)

        assert result.status == "error"
        assert not target.exists()


class TestExpandAll:
    def test_expands_archives_nested_inside_archives(self, tmp_path: Path) -> None:
        inner = tmp_path / "inner.zip"
        _make_zip(inner, {"deep.txt": "found me"})
        with zipfile.ZipFile(tmp_path / "outer.zip", "w") as zf:
            zf.write(inner, arcname="inner.zip")
        inner.unlink()

        results = list(ArchiveExtractor().expand_all(tmp_path))

        assert all(r.status == "expanded" for r in results)
        assert (tmp_path / "outer" / "inner" / "deep.txt").read_text() == "found me"

    def test_each_archive_is_expanded_only_once(self, tmp_path: Path) -> None:
        _make_zip(tmp_path / "a.zip", {"x.txt": "x"})

        results = list(ArchiveExtractor().expand_all(tmp_path))

        assert len(results) == 1

    def test_no_archives_yields_nothing(self, tmp_path: Path) -> None:
        (tmp_path / "plain.txt").write_text("nothing to do")

        assert list(ArchiveExtractor().expand_all(tmp_path)) == []


class TestFolderProcessorIntegration:
    def test_expansion_is_off_unless_the_setting_is_on(self, tmp_path: Path) -> None:
        _make_zip(tmp_path / "reports.zip", {"a.txt": "one"})
        processor = FolderProcessor(file_processor=None)

        results = list(processor.expand_archives(tmp_path, ProcessingSettings()))

        assert results == []
        assert not (tmp_path / "reports").exists()

    def test_expansion_runs_when_the_setting_is_on(self, tmp_path: Path) -> None:
        _make_zip(tmp_path / "reports.zip", {"a.txt": "one"})
        processor = FolderProcessor(file_processor=None)

        results = list(
            processor.expand_archives(tmp_path, ProcessingSettings(expand_archives=True))
        )

        assert [r.status for r in results] == ["expanded"]
        assert (tmp_path / "reports" / "a.txt").read_text() == "one"
