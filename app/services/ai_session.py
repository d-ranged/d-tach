import logging
import secrets
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class AISession:
    """One AI Mode session: the placeholder -> original mapping for one extracted file."""

    replacements: dict[str, str]
    source_path: Path
    created_at: float
    last_accessed: float
    temp_files: list[Path] = field(default_factory=list)


class AISessionStore:
    """In-memory store of AI Mode sessions, keyed by session_id.

    Sessions exist only for the lifetime of one AI conversation and are
    cleared on server restart — deliberately non-durable, since the mapping
    they hold (placeholder -> real value) is the sensitive artefact AI Mode
    exists to keep out of the agent's own context. Idle sessions expire after
    a configurable timeout; their temp files are deleted on expiry.
    """

    def __init__(self, timeout_minutes: int = 60) -> None:
        """Initialise an empty store with the given idle timeout."""
        self._timeout_minutes = timeout_minutes
        self._sessions: dict[str, AISession] = {}
        self._lock = threading.Lock()

    def create(self, replacements: dict[str, str], source_path: Path) -> str:
        """Start a new session for one extracted file and return its session_id."""
        session_id = secrets.token_urlsafe(16)
        now = time.time()
        with self._lock:
            self._expire_locked()
            self._sessions[session_id] = AISession(
                replacements=dict(replacements),
                source_path=source_path,
                created_at=now,
                last_accessed=now,
            )
        return session_id

    def get(self, session_id: str) -> Optional[AISession]:
        """Return the session for session_id, refreshing its idle timer, or None if unknown/expired."""
        with self._lock:
            self._expire_locked()
            session = self._sessions.get(session_id)
            if session is not None:
                session.last_accessed = time.time()
            return session

    def add_temp_file(self, session_id: str, path: Path) -> None:
        """Register a temp file as belonging to session_id so it is cleaned up on expiry."""
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.temp_files.append(path)

    def set_timeout_minutes(self, minutes: int) -> None:
        """Update the idle timeout applied to future expiry checks."""
        self._timeout_minutes = minutes

    def _expire_locked(self) -> None:
        """Remove idle sessions and delete their temp files. Caller must hold self._lock."""
        cutoff = time.time() - self._timeout_minutes * 60
        expired = [sid for sid, session in self._sessions.items() if session.last_accessed < cutoff]
        for sid in expired:
            session = self._sessions.pop(sid)
            for temp_file in session.temp_files:
                try:
                    temp_file.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning("Could not delete expired AI Mode temp file %s: %s", temp_file, exc)
