import hmac
import hashlib
import string
from typing import Final, Optional

_ALPHANUM: Final[str] = string.digits + string.ascii_uppercase  # 36 characters: 0-9A-Z
_HASH_LENGTH: Final[int] = 4
_PREFIX_LENGTH: Final[int] = 2

# Shorter labels used in hashed placeholders for non-name entity types.
# Keeps placeholder length reasonable in output documents.
_ENTITY_LABELS: Final[dict[str, str]] = {
    "EMAIL_ADDRESS": "EMAIL",
    "PHONE_NUMBER":  "PHONE",
    "LOCATION":      "LOC",
    "URL":           "URL",
    "IBAN_CODE":     "IBAN",
    "NL_BSN":        "BSN",
    "NUMERIC_ID":    "ID",
}

# Entity types never hashed even when hashing is on.
# DATE_TIME: dates are not person identifiers; hashing them is meaningless.
# NRP: nationality/religion/politics — not a unique person identifier.
UNHASHABLE_ENTITIES: Final[frozenset[str]] = frozenset({"DATE_TIME", "NRP"})


def _to_alphanum(digest_int: int, length: int) -> str:
    """Convert an integer digest to a fixed-length uppercase alphanumeric string."""
    chars = []
    for _ in range(length):
        chars.append(_ALPHANUM[digest_int % len(_ALPHANUM)])
        digest_int //= len(_ALPHANUM)
    return "".join(chars)


class HashEncoder:
    """Produces consistent pseudonymous hashes using a user-supplied secret.

    Name encoding (PERSON entities):
      First names → ``{first2}-{hash4}``  e.g. ``Craig`` → ``Cr-A2T5``
      Last names  → ``{hash4}``           e.g. ``Bradley`` → ``HY23``

    Non-name entity encoding (emails, phones, IDs, etc.):
      ``[LABEL_XXXX]`` where LABEL is a short form of the entity type and
      XXXX is a 4-char HMAC hash of ``entity_type:value``.
      e.g. ``sarah@example.com`` → ``[EMAIL_A2B3]``

    The same value and secret always produce the same output across sessions.
    """

    def __init__(self, secret: str) -> None:
        """Initialise with the user's secret, used as the HMAC key."""
        if not secret:
            raise ValueError("Secret must not be empty.")
        self._secret: bytes = secret.encode("utf-8")

    def encode_first_name(self, name: str) -> str:
        """Return the encoded first name as ``{first2}-{hash4}``.

        The first two characters are preserved exactly; the remainder is
        hashed to exactly four uppercase alphanumeric characters.
        """
        prefix = name[:_PREFIX_LENGTH]
        remainder = name[_PREFIX_LENGTH:]
        hashed = self._hash(remainder)
        return f"{prefix}-{hashed}"

    def encode_last_name(self, name: str) -> str:
        """Return the encoded last name as a four-character uppercase alphanumeric hash."""
        return self._hash(name)

    def encode_full_name(self, name: str) -> str:
        """Encode a full name by applying first-name and last-name rules to each part.

        The first word is treated as the first name; all remaining words are
        joined and treated as the last name. A single-word name is treated as
        a first name only. This ensures a first name appearing alone in a file
        or folder name resolves to the same value as in a full name.
        """
        parts = name.split()
        if not parts:
            return name
        if len(parts) == 1:
            return self.encode_first_name(parts[0])
        first = self.encode_first_name(parts[0])
        last = self.encode_last_name(" ".join(parts[1:]))
        return f"{first} {last}"

    def encode_value(self, entity_type: str, value: str) -> str:
        """Return a 4-char hash for a non-name PII value.

        The entity_type is included in the HMAC input so the same string value
        in two different entity types produces different outputs. This prevents
        e.g. a student number and an email that happen to share a numeric string
        from collapsing to the same placeholder.
        """
        return self._hash(f"{entity_type}:{value}")

    def encode_entity(self, entity_type: str, value: str) -> Optional[str]:
        """Return the full hashed placeholder for a non-name PII entity.

        Returns ``None`` for entity types that should not be hashed (see
        UNHASHABLE_ENTITIES). The caller should fall back to the sequential
        placeholder in that case.

        For PERSON entities use encode_full_name instead.

        Examples::

            encode_entity("EMAIL_ADDRESS", "foo@bar.com") → "[EMAIL_A2B3]"
            encode_entity("NL_BSN", "123456782")          → "[BSN_C4D1]"
            encode_entity("DATE_TIME", "2025-09-01")      → None
        """
        if entity_type in UNHASHABLE_ENTITIES:
            return None
        label = _ENTITY_LABELS.get(entity_type, entity_type)
        return f"[{label}_{self.encode_value(entity_type, value)}]"

    def _hash(self, value: str) -> str:
        """Return a deterministic four-character uppercase alphanumeric string.

        Uses HMAC-SHA256 with the user secret as key so the output is only
        reproducible by someone who knows the secret.
        """
        digest = hmac.new(
            self._secret,
            value.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return _to_alphanum(int(digest, 16), _HASH_LENGTH)
