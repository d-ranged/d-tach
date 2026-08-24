import json
import logging
import secrets
import tempfile
from pathlib import Path
from typing import Final

from app.services.folder_processor import normalize_extensions
from app.services.pattern_config import PatternConfig

logger = logging.getLogger(__name__)

SETTINGS_FILE: Final[Path] = Path("user_settings.json")

DEFAULT_PORT: Final[int] = 5555
MIN_PORT: Final[int] = 1024
MAX_PORT: Final[int] = 65535

DEFAULT_KNOWN_VALUE_ENTITY_TYPE: Final[str] = "PERSON"
KNOWN_VALUE_SOURCES: Final[tuple[str, ...]] = ("manual", "class_list")
DEFAULT_KNOWN_VALUE_SOURCE: Final[str] = "manual"

DEFAULT_AI_TEMP_DIR: Final[str] = str(Path(tempfile.gettempdir()) / "d-tach-ai")
DEFAULT_AI_SESSION_TIMEOUT_MINUTES: Final[int] = 60
DEFAULT_AI_INLINE_TEXT_MAX_CHARS: Final[int] = 50000

_DEFAULTS: Final[dict] = {
    "hashing_enabled": False,
    "hashing_secret": "",
    "port": DEFAULT_PORT,
    "tray_startup_prompt_shown": False,
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
    "class_list_path": "",
    "class_list_column_mapping": {},
    "restore_input_path": "",
    "restore_keyref_path": "",
    "enabled_languages": ["en"],
    "loading_strategy": "eager",
    "language_setup_complete": False,
    "ai_mode_enabled": False,
    "ai_api_token": "",
    "ai_session_timeout_minutes": DEFAULT_AI_SESSION_TIMEOUT_MINUTES,
    "ai_inline_text_max_chars": DEFAULT_AI_INLINE_TEXT_MAX_CHARS,
    "ai_temp_dir": DEFAULT_AI_TEMP_DIR,
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
    def port(self) -> int:
        """The port the Flask server listens on (default 5555)."""
        return self._data.get("port", DEFAULT_PORT)

    @port.setter
    def port(self, value: int) -> None:
        value = int(value)
        if not (MIN_PORT <= value <= MAX_PORT):
            raise ValueError(f"port must be between {MIN_PORT} and {MAX_PORT}, got {value!r}.")
        self._data["port"] = value

    @property
    def tray_startup_prompt_shown(self) -> bool:
        """Whether the one-time 'run at startup?' prompt has already been shown."""
        return self._data.get("tray_startup_prompt_shown", False)

    @tray_startup_prompt_shown.setter
    def tray_startup_prompt_shown(self, value: bool) -> None:
        self._data["tray_startup_prompt_shown"] = bool(value)

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
    def known_values(self) -> list[dict]:
        """Persistent typed values always anonymized regardless of NER detection.

        Each entry is a dict: {"value": str, "entity_type": str, "source": "manual" | "class_list"}.
        """
        return [dict(v) for v in self._data.get("known_values", [])]

    @known_values.setter
    def known_values(self, value: list[dict]) -> None:
        self._data["known_values"] = [UserSettings._normalize_known_value(v) for v in value]

    @staticmethod
    def _normalize_known_value(entry: dict) -> dict:
        """Coerce one known-value entry to the canonical {value, entity_type, source} shape."""
        value = str(entry.get("value", "")).strip()
        entity_type = str(entry.get("entity_type") or DEFAULT_KNOWN_VALUE_ENTITY_TYPE)
        source = entry.get("source")
        if source not in KNOWN_VALUE_SOURCES:
            source = DEFAULT_KNOWN_VALUE_SOURCE
        return {"value": value, "entity_type": entity_type, "source": source}

    @property
    def class_list_path(self) -> str:
        """Path of the last-imported class list file, remembered for Re-sync."""
        return self._data.get("class_list_path", "")

    @class_list_path.setter
    def class_list_path(self, value: str) -> None:
        self._data["class_list_path"] = str(value)

    @property
    def class_list_column_mapping(self) -> dict[str, str]:
        """Remembered header -> entity_type mapping for the class list, used by Re-sync."""
        return dict(self._data.get("class_list_column_mapping", {}))

    @class_list_column_mapping.setter
    def class_list_column_mapping(self, value: dict[str, str]) -> None:
        self._data["class_list_column_mapping"] = {str(k): str(v) for k, v in value.items()}

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

    @property
    def enabled_languages(self) -> list[str]:
        """Language codes the user has enabled for detection/loading."""
        return list(self._data.get("enabled_languages", ["en"]))

    @enabled_languages.setter
    def enabled_languages(self, value: list[str]) -> None:
        self._data["enabled_languages"] = [str(v) for v in value]

    @property
    def loading_strategy(self) -> str:
        """How language models are loaded: 'eager' (all at startup) or 'lazy' (on demand)."""
        return self._data.get("loading_strategy", "eager")

    @loading_strategy.setter
    def loading_strategy(self, value: str) -> None:
        if value not in ("eager", "lazy"):
            raise ValueError(f"loading_strategy must be 'eager' or 'lazy', got {value!r}.")
        self._data["loading_strategy"] = value

    @property
    def language_setup_complete(self) -> bool:
        """Whether the first-launch language-selection screen has been completed."""
        return self._data.get("language_setup_complete", False)

    @language_setup_complete.setter
    def language_setup_complete(self, value: bool) -> None:
        self._data["language_setup_complete"] = bool(value)

    @property
    def ai_mode_enabled(self) -> bool:
        """Whether the local AI Mode HTTP API is active. Off by default."""
        return self._data.get("ai_mode_enabled", False)

    @ai_mode_enabled.setter
    def ai_mode_enabled(self, value: bool) -> None:
        self._data["ai_mode_enabled"] = bool(value)
        if self._data["ai_mode_enabled"] and not self._data.get("ai_api_token"):
            self._data["ai_api_token"] = secrets.token_urlsafe(32)

    @property
    def ai_api_token(self) -> str:
        """The bearer token AI Mode requests must present via the X-D-Tach-Token header."""
        return self._data.get("ai_api_token", "")

    def regenerate_ai_api_token(self) -> str:
        """Generate and store a new AI Mode API token, invalidating the previous one, and return it."""
        self._data["ai_api_token"] = secrets.token_urlsafe(32)
        return self._data["ai_api_token"]

    @property
    def ai_session_timeout_minutes(self) -> int:
        """Idle timeout, in minutes, before an AI Mode session and its temp files expire."""
        return self._data.get("ai_session_timeout_minutes", DEFAULT_AI_SESSION_TIMEOUT_MINUTES)

    @ai_session_timeout_minutes.setter
    def ai_session_timeout_minutes(self, value: int) -> None:
        value = int(value)
        if value < 1:
            raise ValueError(f"ai_session_timeout_minutes must be at least 1, got {value!r}.")
        self._data["ai_session_timeout_minutes"] = value

    @property
    def ai_inline_text_max_chars(self) -> int:
        """Character threshold above which extracted/restored text is written to ai_temp_dir instead of inlined."""
        return self._data.get("ai_inline_text_max_chars", DEFAULT_AI_INLINE_TEXT_MAX_CHARS)

    @ai_inline_text_max_chars.setter
    def ai_inline_text_max_chars(self, value: int) -> None:
        value = int(value)
        if value < 1:
            raise ValueError(f"ai_inline_text_max_chars must be at least 1, got {value!r}.")
        self._data["ai_inline_text_max_chars"] = value

    @property
    def ai_temp_dir(self) -> str:
        """Directory AI Mode writes large extracted/restored text files to."""
        return self._data.get("ai_temp_dir") or DEFAULT_AI_TEMP_DIR

    @ai_temp_dir.setter
    def ai_temp_dir(self, value: str) -> None:
        self._data["ai_temp_dir"] = str(value)

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
        d["class_list_column_mapping"] = dict(_DEFAULTS["class_list_column_mapping"])
        return d



    @staticmethod
    def _merge_with_defaults(raw: dict) -> dict:
        """Return raw data with any missing keys filled from defaults."""
        merged = UserSettings._fresh_defaults()
        if isinstance(raw.get("hashing_enabled"), bool):
            merged["hashing_enabled"] = raw["hashing_enabled"]
        if isinstance(raw.get("hashing_secret"), str):
            merged["hashing_secret"] = raw["hashing_secret"]
        if isinstance(raw.get("port"), int) and MIN_PORT <= raw["port"] <= MAX_PORT:
            merged["port"] = raw["port"]
        if isinstance(raw.get("tray_startup_prompt_shown"), bool):
            merged["tray_startup_prompt_shown"] = raw["tray_startup_prompt_shown"]
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
            migrated: list[dict] = []
            for v in raw["known_values"]:
                if isinstance(v, str) and v.strip():
                    # Pre-Step-4 format: plain strings, always PERSON, manually added.
                    migrated.append({
                        "value": v.strip(),
                        "entity_type": DEFAULT_KNOWN_VALUE_ENTITY_TYPE,
                        "source": DEFAULT_KNOWN_VALUE_SOURCE,
                    })
                elif isinstance(v, dict) and str(v.get("value", "")).strip():
                    migrated.append(UserSettings._normalize_known_value(v))
            merged["known_values"] = migrated
        if isinstance(raw.get("class_list_path"), str):
            merged["class_list_path"] = raw["class_list_path"]
        if isinstance(raw.get("class_list_column_mapping"), dict):
            merged["class_list_column_mapping"] = {
                str(k): str(v) for k, v in raw["class_list_column_mapping"].items()
            }
        if isinstance(raw.get("restore_input_path"), str):
            merged["restore_input_path"] = raw["restore_input_path"]
        if isinstance(raw.get("restore_keyref_path"), str):
            merged["restore_keyref_path"] = raw["restore_keyref_path"]

        # Language management fields (issue #62): a settings file written before
        # this field existed belongs to an existing install that already relied
        # on both en+nl being loaded — grandfather it in as fully set up, rather
        # than surprising an upgrading user with the first-launch setup screen
        # or dropping Dutch support they were already using.
        is_pre_language_management = "language_setup_complete" not in raw
        if isinstance(raw.get("enabled_languages"), list):
            langs = [str(v) for v in raw["enabled_languages"] if isinstance(v, str) and v.strip()]
            merged["enabled_languages"] = langs or merged["enabled_languages"]
        elif is_pre_language_management:
            merged["enabled_languages"] = ["en", "nl"]
        if raw.get("loading_strategy") in ("eager", "lazy"):
            merged["loading_strategy"] = raw["loading_strategy"]
        if isinstance(raw.get("language_setup_complete"), bool):
            merged["language_setup_complete"] = raw["language_setup_complete"]
        elif is_pre_language_management:
            merged["language_setup_complete"] = True

        if isinstance(raw.get("ai_mode_enabled"), bool):
            merged["ai_mode_enabled"] = raw["ai_mode_enabled"]
        if isinstance(raw.get("ai_api_token"), str):
            merged["ai_api_token"] = raw["ai_api_token"]
        if isinstance(raw.get("ai_session_timeout_minutes"), int) and raw["ai_session_timeout_minutes"] >= 1:
            merged["ai_session_timeout_minutes"] = raw["ai_session_timeout_minutes"]
        if isinstance(raw.get("ai_inline_text_max_chars"), int) and raw["ai_inline_text_max_chars"] >= 1:
            merged["ai_inline_text_max_chars"] = raw["ai_inline_text_max_chars"]
        if isinstance(raw.get("ai_temp_dir"), str) and raw["ai_temp_dir"].strip():
            merged["ai_temp_dir"] = raw["ai_temp_dir"]

        return merged
