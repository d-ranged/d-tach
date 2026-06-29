import json
import logging
from pathlib import Path
from typing import Final

from app.services.folder_processor import normalize_extensions
from app.services.pattern_config import PatternConfig

logger = logging.getLogger(__name__)

SETTINGS_FILE: Final[Path] = Path("user_settings.json")

_DEFAULTS: Final[dict] = {
    "hashing_enabled": False,
    "hashing_secret": "",
    "language": "en",
    "anonymize_dates": False,
    "anonymize_locations": False,
    "anonymize_urls": False,
    "pattern_config": {
        "digit_count": 7,
        "check_file_names": False,
        "numeric_id_enabled": False,
    },
    "excel_generic_enabled": True,
    "excel_column_names": "",
    "output_mode": "prefix",
    "pass_through_extensions": "",
    "known_values": [],
    "restore_input_path": "",
    "restore_keyref_path": "",
}


class UserSettings:
    """Persists user preferences to a local JSON file and restores them on launch.

    Stores: hashing toggle state, hashing secret, selected language,
    anonymize dates toggle, PatternConfig settings, and Excel-specific settings.
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
    def anonymize_locations(self) -> bool:
        """Whether LOCATION entities should be anonymized (off by default — often meaningful context)."""
        return self._data.get("anonymize_locations", False)

    @anonymize_locations.setter
    def anonymize_locations(self, value: bool) -> None:
        self._data["anonymize_locations"] = bool(value)

    @property
    def anonymize_urls(self) -> bool:
        """Whether URL entities should be anonymized (off by default — overlaps with emails)."""
        return self._data.get("anonymize_urls", False)

    @anonymize_urls.setter
    def anonymize_urls(self, value: bool) -> None:
        self._data["anonymize_urls"] = bool(value)

    @property
    def pattern_config(self) -> PatternConfig:
        """The active PatternConfig instance."""
        return PatternConfig.from_dict(self._data["pattern_config"])

    @pattern_config.setter
    def pattern_config(self, config: PatternConfig) -> None:
        self._data["pattern_config"] = config.to_dict()

    @property
    def excel_generic_enabled(self) -> bool:
        """Whether NER-based generic anonymization runs on Excel string cells."""
        return self._data.get("excel_generic_enabled", True)

    @excel_generic_enabled.setter
    def excel_generic_enabled(self, value: bool) -> None:
        self._data["excel_generic_enabled"] = bool(value)

    @property
    def excel_column_names(self) -> list[str]:
        """Column names to anonymize by exact column match (parsed from stored string)."""
        raw = self._data.get("excel_column_names", "")
        return [c.strip() for c in raw.split(",") if c.strip()]

    @excel_column_names.setter
    def excel_column_names(self, value: list[str]) -> None:
        self._data["excel_column_names"] = ", ".join(value)

    @property
    def output_mode(self) -> str:
        """Folder output mode: 'prefix' (default) or 'subfolder'."""
        return self._data.get("output_mode", "prefix")

    @output_mode.setter
    def output_mode(self, value: str) -> None:
        if value not in ("prefix", "subfolder"):
            raise ValueError(f"output_mode must be 'prefix' or 'subfolder', got {value!r}")
        self._data["output_mode"] = value

    @property
    def pass_through_extensions(self) -> list[str]:
        """Extensions copied verbatim in folder mode without PII scanning (empty by default)."""
        return normalize_extensions(self._data.get("pass_through_extensions", ""))

    @pass_through_extensions.setter
    def pass_through_extensions(self, value: list[str]) -> None:
        self._data["pass_through_extensions"] = ", ".join(value)

    @property
    def known_values(self) -> list[str]:
        """Persistent list of strings always anonymized regardless of NER detection."""
        return list(self._data.get("known_values", []))

    @known_values.setter
    def known_values(self, value: list[str]) -> None:
        self._data["known_values"] = [str(v) for v in value]

    @property
    def restore_input_path(self) -> str:
        """Last-used input file path for the Restore tab."""
        return self._data.get("restore_input_path", "")

    @restore_input_path.setter
    def restore_input_path(self, value: str) -> None:
        self._data["restore_input_path"] = str(value)

    @property
    def restore_keyref_path(self) -> str:
        """Last-used KEYREF file path for the Restore tab."""
        return self._data.get("restore_keyref_path", "")

    @restore_keyref_path.setter
    def restore_keyref_path(self, value: str) -> None:
        self._data["restore_keyref_path"] = str(value)

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
        if isinstance(raw.get("anonymize_locations"), bool):
            merged["anonymize_locations"] = raw["anonymize_locations"]
        if isinstance(raw.get("anonymize_urls"), bool):
            merged["anonymize_urls"] = raw["anonymize_urls"]
        if isinstance(raw.get("pattern_config"), dict):
            pc = raw["pattern_config"]
            if isinstance(pc.get("digit_count"), int):
                merged["pattern_config"]["digit_count"] = pc["digit_count"]
            if isinstance(pc.get("check_file_names"), bool):
                merged["pattern_config"]["check_file_names"] = pc["check_file_names"]
            # Accept both old key name and new for forward compatibility
            if isinstance(pc.get("numeric_id_enabled"), bool):
                merged["pattern_config"]["numeric_id_enabled"] = pc["numeric_id_enabled"]
            elif isinstance(pc.get("student_number_enabled"), bool):
                merged["pattern_config"]["numeric_id_enabled"] = pc["student_number_enabled"]
        if isinstance(raw.get("excel_generic_enabled"), bool):
            merged["excel_generic_enabled"] = raw["excel_generic_enabled"]
        if isinstance(raw.get("excel_column_names"), str):
            merged["excel_column_names"] = raw["excel_column_names"]
        if raw.get("output_mode") in ("prefix", "subfolder"):
            merged["output_mode"] = raw["output_mode"]
        if isinstance(raw.get("pass_through_extensions"), str):
            merged["pass_through_extensions"] = raw["pass_through_extensions"]
        if isinstance(raw.get("known_values"), list):
            merged["known_values"] = [str(v) for v in raw["known_values"] if isinstance(v, str) and v.strip()]
        if isinstance(raw.get("restore_input_path"), str):
            merged["restore_input_path"] = raw["restore_input_path"]
        if isinstance(raw.get("restore_keyref_path"), str):
            merged["restore_keyref_path"] = raw["restore_keyref_path"]
        return merged
