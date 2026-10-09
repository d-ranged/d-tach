import csv
from pathlib import Path

from app.services.document_processor import DocumentProcessor

HTTP_NOT_FOUND = 404
HTTP_BAD_REQUEST = 400


class KeyrefError(Exception):
    """A KEYREF file could not be used; carries the HTTP status a route should return."""

    def __init__(self, message: str, status: int) -> None:
        """Store the user-facing message and the matching HTTP status."""
        super().__init__(message)
        self.message = message
        self.status = status


def read_keyref(keyref_path_str: str) -> dict[str, str]:
    """Return {placeholder: original} from a KEYREF CSV, or raise KeyrefError.

    The one reader behind both Document Mode's /restore and AI Mode's
    /ai/restore, so the wording of each failure lives in a single place.
    """
    path = Path(keyref_path_str)
    if not path.exists():
        raise KeyrefError(f"KEYREF file not found: {keyref_path_str}", HTTP_NOT_FOUND)
    if not path.is_file():
        raise KeyrefError(f"KEYREF path is not a file: {keyref_path_str}", HTTP_BAD_REQUEST)
    try:
        mapping = DocumentProcessor.load_keyref_csv(path)
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise KeyrefError(f"Could not read KEYREF file: {exc}", HTTP_BAD_REQUEST) from exc
    if not mapping:
        raise KeyrefError("KEYREF file contained no placeholder mappings.", HTTP_BAD_REQUEST)
    return mapping
