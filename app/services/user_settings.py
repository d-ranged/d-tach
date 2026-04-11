import json
import logging
from pathlib import Path
from typing import Final

from app.services.pattern_config import PatternConfig

logger = logging.getLogger(__name__)

SETTINGS_FILE: Final[Path] = Path("user_settings.json")

_DEFAULTS: Final[dict] = {
    "hashing_enabled": False,
    "hashing_secret": "",
    "language": "en",
    "anonymize_dates": False,
    "pattern_config": {
        "digit_count": 7,
        "check_file_names": False,
    },
}


class UserSettings:
    """Persists user preferences to a local JSON file and restores them on launch.

    Stores: hashing toggle state, hashing secret, selected language,
    anonymize dates toggle, and PatternConfig settings.
    The settings file is excluded from version control (see .gitignore).
    """

    def __init__(self, settings_path: Path = SETTINGS_FILE) -> None:
        """Load settings from disk, creating defaults if the file is absent."""
        self._path = settings_path
        self._data: dict = {}
        self._load()

    # ------------------------------------------------------------------
    # Public properties
    # ------------------------------------------------------------------

    @property
    def hashing_enabled(self) -> bool:
        """Whether name hashing is currently enabled."""
        return self._data["hashing_enabled"]

    @hashing_enabled.setter
    def hashing_enabled(self, value: bool) -> None:
        self._data["hashing_enabled"] = bool(value)

    @property
    def hashing_secret(self) -> str:
        """The user-supplied hashing secret (empty string when not set)."""
        return self._data["hashing_secret"]

    @hashing_secret.setter
    def hashing_secret(self, value: str) -> None:
        self._data["hashing_secret"] = str(value)

    @property
    def language(self) -> str:
        """The user-selected processing language ('en' or 'nl')."""
        return self._data["language"]

    @language.setter
    def language(self, value: str) -> None:
        if value not in ("en", "nl"):
            raise ValueError(f"language must be 'en' or 'nl', got {value!r}.")
        self._data["language"] = value

    @property
    def anonymize_dates(self) -> bool:
        """Whether DATE_TIME entities should be anonymized."""
        return self._data["anonymize_dates"]

    @anonymize_dates.setter
    def anonymize_dates(self, value: bool) -> None:
        self._data["anonymize_dates"] = bool(value)

    @property
    def pattern_config(self) -> PatternConfig:
        """The active PatternConfig instance."""
        return PatternConfig.from_dict(self._data["pattern_config"])

    @pattern_config.setter
    def pattern_config(self, config: PatternConfig) -> None:
        self._data["pattern_config"] = config.to_dict()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self) -> None:
        """Write current settings to disk."""
        try:
            self._path.write_text(
                json.dumps(self._data, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            logger.error("Failed to save settings to %s: %s", self._path, exc)
            raise

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _load(self) -> None:
        """Read settings from disk, falling back to defaults on any error."""
        if not self._path.exists():
            self._data = self._fresh_defaults()
            return

        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._data = self._merge_with_defaults(raw)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning(
                "Could not read settings from %s (%s); using defaults.", self._path, exc
            )
            self._data = self._fresh_defaults()

    @staticmethod
    def _fresh_defaults() -> dict:
        """Return a fresh copy of the default settings dict."""
        d = dict(_DEFAULTS)
        d["pattern_config"] = dict(_DEFAULTS["pattern_config"])
        return d

    @staticmethod
    def _merge_with_defaults(raw: dict) -> dict:
        """Return raw data with any missing keys filled from defaults."""
        merged = UserSettings._fresh_defaults()
        if isinstance(raw.get("hashing_enabled"), bool):
            merged["hashing_enabled"] = raw["hashing_enabled"]
        if isinstance(raw.get("hashing_secret"), str):
            merged["hashing_secret"] = raw["hashing_secret"]
        if raw.get("language") in ("en", "nl"):
            merged["language"] = raw["language"]
        if isinstance(raw.get("anonymize_dates"), bool):
            merged["anonymize_dates"] = raw["anonymize_dates"]
        if isinstance(raw.get("pattern_config"), dict):
            pc = raw["pattern_config"]
            if isinstance(pc.get("digit_count"), int):
                merged["pattern_config"]["digit_count"] = pc["digit_count"]
            if isinstance(pc.get("check_file_names"), bool):
                merged["pattern_config"]["check_file_names"] = pc["check_file_names"]
        return merged
