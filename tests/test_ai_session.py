"""Tests for the AISessionStore service class (issue #68 — AI Mode)."""

from pathlib import Path

import pytest

from app.services import ai_session as ai_session_module
from app.services.ai_session import AISessionStore


class _FakeClock:
    """Controllable stand-in for time.time() so expiry can be tested without sleeping."""

    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _FakeClock:
    fake = _FakeClock()
    monkeypatch.setattr(ai_session_module.time, "time", fake)
    return fake


@pytest.fixture
def store() -> AISessionStore:
    return AISessionStore(timeout_minutes=60)


class TestCreateAndGet:
    def test_create_returns_a_session_id(self, store: AISessionStore) -> None:
        session_id = store.create({"[PERSON_1]": "John Smith"}, Path("source.docx"))
        assert isinstance(session_id, str) and session_id

    def test_get_returns_the_created_session(self, store: AISessionStore) -> None:
        session_id = store.create({"[PERSON_1]": "John Smith"}, Path("source.docx"))
        session = store.get(session_id)
        assert session is not None
        assert session.replacements == {"[PERSON_1]": "John Smith"}
        assert session.source_path == Path("source.docx")

    def test_get_unknown_session_id_returns_none(self, store: AISessionStore) -> None:
        assert store.get("does-not-exist") is None

    def test_two_sessions_get_different_ids(self, store: AISessionStore) -> None:
        first = store.create({}, Path("a.docx"))
        second = store.create({}, Path("b.docx"))
        assert first != second

    def test_create_copies_replacements_dict(self, store: AISessionStore) -> None:
        source = {"[PERSON_1]": "John Smith"}
        session_id = store.create(source, Path("source.docx"))
        source["[PERSON_2]"] = "Jane Doe"
        session = store.get(session_id)
        assert session is not None
        assert "[PERSON_2]" not in session.replacements


class TestExpiry:
    def test_session_available_before_timeout(self, store: AISessionStore, clock: _FakeClock) -> None:
        session_id = store.create({}, Path("a.docx"))
        clock.advance(59 * 60)
        assert store.get(session_id) is not None

    def test_session_expires_after_timeout(self, store: AISessionStore, clock: _FakeClock) -> None:
        session_id = store.create({}, Path("a.docx"))
        clock.advance(61 * 60)
        assert store.get(session_id) is None

    def test_get_refreshes_the_idle_timer(self, store: AISessionStore, clock: _FakeClock) -> None:
        session_id = store.create({}, Path("a.docx"))
        clock.advance(59 * 60)
        assert store.get(session_id) is not None  # refreshes last_accessed
        clock.advance(59 * 60)
        assert store.get(session_id) is not None  # would be expired without the refresh above

    def test_set_timeout_minutes_changes_expiry_threshold(
        self, store: AISessionStore, clock: _FakeClock
    ) -> None:
        session_id = store.create({}, Path("a.docx"))
        store.set_timeout_minutes(5)
        clock.advance(6 * 60)
        assert store.get(session_id) is None


class TestTempFileCleanup:
    def test_temp_file_deleted_when_session_expires(
        self, store: AISessionStore, clock: _FakeClock, tmp_path: Path
    ) -> None:
        temp_file = tmp_path / "extracted.txt"
        temp_file.write_text("anonymized text", encoding="utf-8")

        session_id = store.create({}, Path("a.docx"))
        store.add_temp_file(session_id, temp_file)

        clock.advance(61 * 60)
        store.get(session_id)  # any store access triggers the expiry sweep

        assert not temp_file.exists()

    def test_missing_temp_file_does_not_raise(
        self, store: AISessionStore, clock: _FakeClock, tmp_path: Path
    ) -> None:
        temp_file = tmp_path / "already-gone.txt"
        session_id = store.create({}, Path("a.docx"))
        store.add_temp_file(session_id, temp_file)

        clock.advance(61 * 60)
        store.get(session_id)  # must not raise even though temp_file was never created

    def test_add_temp_file_on_unknown_session_is_a_no_op(
        self, store: AISessionStore, tmp_path: Path
    ) -> None:
        store.add_temp_file("does-not-exist", tmp_path / "file.txt")  # must not raise
