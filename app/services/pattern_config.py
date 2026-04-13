from typing import Final

MIN_DIGIT_COUNT: Final[int] = 4
MAX_DIGIT_COUNT: Final[int] = 12
DEFAULT_DIGIT_COUNT: Final[int] = 7

CURRENCY_SYMBOLS: Final[str] = "€$£"


class PatternConfig:
    """Holds active custom pattern detection settings.

    Controls numeric ID detection (exact digit count, enable toggle) and
    whether file and folder names are included in PII scanning.
    """

    def __init__(
        self,
        digit_count: int = DEFAULT_DIGIT_COUNT,
        check_file_names: bool = False,
        numeric_id_enabled: bool = False,
    ) -> None:
        """Initialise with validated settings.

        Raises ValueError if digit_count is outside the allowed range.
        """
        self.digit_count = digit_count
        self.check_file_names = check_file_names
        self.numeric_id_enabled = numeric_id_enabled

    @property
    def digit_count(self) -> int:
        """Exact number of consecutive digits that constitute a numeric ID."""
        return self._digit_count

    @digit_count.setter
    def digit_count(self, value: int) -> None:
        """Validate and set the digit count."""
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(
                f"digit_count must be an integer, got {type(value).__name__}."
            )
        if not (MIN_DIGIT_COUNT <= value <= MAX_DIGIT_COUNT):
            raise ValueError(
                f"digit_count must be between {MIN_DIGIT_COUNT} and "
                f"{MAX_DIGIT_COUNT}, got {value}."
            )
        self._digit_count = value

    def build_numeric_id_regex(self) -> str:
        """Return a regex pattern matching exactly digit_count digits.

        Requires a non-digit (or string boundary) on each side and excludes
        sequences immediately preceded by a currency symbol (€, $, £).
        """
        n = self._digit_count
        return rf"(?<![{CURRENCY_SYMBOLS}\d])\d{{{n}}}(?!\d)"

    def to_dict(self) -> dict:
        """Serialise settings to a plain dict for JSON storage."""
        return {
            "digit_count": self._digit_count,
            "check_file_names": self.check_file_names,
            "numeric_id_enabled": self.numeric_id_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PatternConfig":
        """Deserialise settings from a plain dict."""
        return cls(
            digit_count=data.get("digit_count", DEFAULT_DIGIT_COUNT),
            check_file_names=data.get("check_file_names", False),
            # Accept both old key name (student_number_enabled) and new for migration
            numeric_id_enabled=data.get(
                "numeric_id_enabled", data.get("student_number_enabled", False)
            ),
        )
