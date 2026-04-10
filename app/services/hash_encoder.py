import hmac
import hashlib
import string
from typing import Final

_ALPHANUM: Final[str] = string.digits + string.ascii_uppercase  # 36 characters: 0-9A-Z
_HASH_LENGTH: Final[int] = 4
_PREFIX_LENGTH: Final[int] = 2


def _to_alphanum(digest_int: int, length: int) -> str:
    """Convert an integer digest to a fixed-length uppercase alphanumeric string."""
    chars = []
    for _ in range(length):
        chars.append(_ALPHANUM[digest_int % len(_ALPHANUM)])
        digest_int //= len(_ALPHANUM)
    return "".join(chars)


class HashEncoder:
    """Produces consistent pseudonymous hashes for names using a user-supplied secret.

    First names are encoded as ``{first2}-{hash4}`` (e.g. ``Craig`` → ``Cr-A2T5``).
    Last names are encoded as ``{hash4}`` (e.g. ``Bradley`` → ``HY23``).

    The same name and secret always produce the same output across sessions.
    First and last names are hashed independently so a first name appearing
    alone in a file or folder name resolves to the same value as when it
    appears as part of a full name.
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
