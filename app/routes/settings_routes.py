from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from app.services.class_list_importer import ColumnMappingError
from app.services.folder_processor import normalize_extensions
from app.services.user_settings import MAX_PORT, MIN_PORT

bp = Blueprint("settings", __name__)


@bp.route("/settings")
def settings_page():
    """Render the Settings page."""
    settings = current_app.user_settings
    registry = current_app.language_registry
    installed = set(registry.installed_languages())
    loaded = set(registry.loaded_languages())
    enabled = set(settings.enabled_languages)
    languages_view = [
        {
            "code": lang.code,
            "name": lang.name,
            "download_size_mb": lang.download_size_mb,
            "installed": lang.code in installed,
            "loaded": lang.code in loaded,
            "enabled": lang.code in enabled,
        }
        for lang in registry.supported_languages()
    ]
    return render_template(
        "settings.html",
        active_mode="settings",
        port=settings.port,
        min_port=MIN_PORT,
        max_port=MAX_PORT,
        languages=languages_view,
        loading_strategy=settings.loading_strategy,
        hashing_enabled=settings.hashing_enabled,
        hashing_secret=settings.hashing_secret,
        default_language=settings.language,
        anonymize_dates=settings.anonymize_dates,
        anonymize_locations=settings.anonymize_locations,
        anonymize_urls=settings.anonymize_urls,
        pattern_config=settings.pattern_config,
        excel_generic_enabled=settings.excel_generic_enabled,
        excel_column_names=", ".join(settings.excel_column_names),
        output_mode=settings.output_mode,
        pass_through_extensions=", ".join(settings.pass_through_extensions),
        ai_mode_enabled=settings.ai_mode_enabled,
        ai_api_token=settings.ai_api_token,
        ai_session_timeout_minutes=settings.ai_session_timeout_minutes,
        ai_inline_text_max_chars=settings.ai_inline_text_max_chars,
        ai_temp_dir=settings.ai_temp_dir,
        ai_instructions=_build_ai_instructions(settings.port, settings.ai_api_token),
    )


@bp.route("/settings/port", methods=["POST"])
def update_port():
    """Update the configured port. Takes effect after restart.

    Body: {"port": 5555}
    Returns {"port": <int>} on success, {"error": "..."} on invalid input.
    """
    data = request.get_json(force=True, silent=True) or {}
    raw_port = data.get("port")
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        return jsonify({"error": "Port must be a whole number."}), 400

    settings = current_app.user_settings
    try:
        settings.port = port
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    settings.save()

    return jsonify({"port": settings.port})


@bp.route("/settings/known-values", methods=["GET"])
def get_known_values():
    """Return the current known values list plus the remembered class list state."""
    settings = current_app.user_settings
    return jsonify({
        "values": settings.known_values,
        "class_list_path": settings.class_list_path,
        "class_list_column_mapping": settings.class_list_column_mapping,
    })


@bp.route("/settings/known-values", methods=["POST"])
def add_known_value():
    """Append a manually-entered value to the known values list.

    Body: {"value": "Name to always anonymize"}
    Silently ignores duplicates (case-insensitive comparison against every
    existing entry regardless of source). Always tagged entity_type PERSON,
    source manual. Returns the updated list.
    """
    data = request.get_json(force=True, silent=True) or {}
    value = str(data.get("value", "")).strip()
    if not value:
        return jsonify({"error": "Value cannot be empty."}), 400

    settings = current_app.user_settings
    current = settings.known_values
    if not any(v["value"].lower() == value.lower() for v in current):
        current.append({"value": value, "entity_type": "PERSON", "source": "manual"})
        settings.known_values = current
        settings.save()

    return jsonify({"values": settings.known_values})


@bp.route("/settings/known-values", methods=["DELETE"])
def remove_known_value():
    """Remove a value from the known values list (case-insensitive), any source.

    Body: {"value": "Name to remove"}
    Returns the updated list.
    """
    data = request.get_json(force=True, silent=True) or {}
    value = str(data.get("value", "")).strip()

    settings = current_app.user_settings
    updated = [v for v in settings.known_values if v["value"].lower() != value.lower()]
    settings.known_values = updated
    settings.save()

    return jsonify({"values": settings.known_values})


@bp.route("/settings/known-values/class-list/columns", methods=["POST"])
def class_list_columns():
    """Read the header row of a class list Excel file.

    Body: {"file_path": "C:/roster.xlsx"}
    Returns {"columns": [str, ...]} or {"error": "..."}.
    """
    data = request.get_json(force=True, silent=True) or {}
    file_path, error = _validate_xlsx_path(data.get("file_path", ""))
    if error:
        return jsonify({"error": error}), 400

    try:
        columns = current_app.class_list_importer.read_columns(file_path)
    except Exception as exc:
        return jsonify({"error": f"Could not read columns: {exc}"}), 400

    return jsonify({"columns": columns})


@bp.route("/settings/known-values/class-list/import", methods=["POST"])
def class_list_import():
    """Import known values from a class list using a column mapping.

    Body: {"file_path": "C:/roster.xlsx", "column_mapping": {"Name": "FULL_NAME"}}
    Column types: FIRST_NAME, SURNAME, FULL_NAME, NUMERIC_ID, EMAIL_ADDRESS.
    Each student row gives a full name, first name and surname, each with its
    matching rule. Merges them into the existing known values list (matched
    case-insensitively across all sources), remembers the file path and
    mapping for Re-sync, and returns import counts.
    """
    data = request.get_json(force=True, silent=True) or {}
    file_path, error = _validate_xlsx_path(data.get("file_path", ""))
    if error:
        return jsonify({"error": error}), 400

    column_mapping = data.get("column_mapping")
    if not isinstance(column_mapping, dict) or not column_mapping:
        return jsonify({"error": "column_mapping must be a non-empty object."}), 400

    settings = current_app.user_settings
    try:
        updated_values, result = current_app.class_list_importer.import_from_file(
            file_path, column_mapping, settings.known_values
        )
    except ColumnMappingError as exc:
        return jsonify({"error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"error": f"Import failed: {exc}"}), 400

    settings.known_values = updated_values
    settings.class_list_path = str(file_path)
    settings.class_list_column_mapping = column_mapping
    settings.save()

    return jsonify({
        "added": result.added,
        "updated": result.updated,
        "already_present": result.already_present,
        "full_name_only": result.full_name_only,
        "capital_only": result.capital_only,
        "total_known_values": result.total_known_values,
    })


@bp.route("/settings/known-values/class-list/clear", methods=["DELETE"])
def class_list_clear():
    """Remove every class-list-sourced known value; manual entries are untouched."""
    settings = current_app.user_settings
    settings.known_values = [v for v in settings.known_values if v["source"] != "class_list"]
    settings.save()
    return jsonify({"values": settings.known_values})


def _validate_xlsx_path(file_path_str: str) -> tuple[Path, str]:
    """Validate a class-list file path; return (path, "") or (Path(), error message)."""
    file_path_str = str(file_path_str).strip()
    if not file_path_str:
        return Path(), "No file path provided."
    file_path = Path(file_path_str)
    if file_path.suffix.lower() != ".xlsx":
        return Path(), "Class list must be an .xlsx file."
    if not file_path.exists():
        return Path(), f"File not found: {file_path_str}"
    if not file_path.is_file():
        return Path(), f"Path is not a file: {file_path_str}"
    return file_path, ""


@bp.route("/settings/languages/install", methods=["POST"])
def install_language():
    """Start a background download of a language's spaCy model.

    Body: {"code": "nl"}
    Returns {"state": "downloading"} immediately; poll install-status for completion.
    """
    data = request.get_json(force=True, silent=True) or {}
    code = str(data.get("code", ""))

    registry = current_app.language_registry
    if registry.info(code) is None:
        return jsonify({"error": f"Unsupported language: {code!r}"}), 400

    if registry.is_installed(code):
        return jsonify(registry.download_status(code))

    registry.start_download(code)
    return jsonify(registry.download_status(code))


@bp.route("/settings/languages/install-status", methods=["GET"])
def language_install_status():
    """Return the current download status for a language.

    Query: ?code=nl
    Returns {"state": "idle"|"downloading"|"done"|"error", "message": str}.
    """
    code = request.args.get("code", "")
    registry = current_app.language_registry
    if registry.info(code) is None:
        return jsonify({"error": f"Unsupported language: {code!r}"}), 400

    return jsonify(registry.download_status(code))


@bp.route("/settings/languages/remove", methods=["POST"])
def remove_language():
    """Uninstall a language's spaCy model and disable it. Applies straight away.

    Body: {"code": "nl"}
    """
    data = request.get_json(force=True, silent=True) or {}
    code = str(data.get("code", ""))

    registry = current_app.language_registry
    if registry.info(code) is None:
        return jsonify({"error": f"Unsupported language: {code!r}"}), 400

    try:
        registry.remove(code)
    except Exception as exc:
        return jsonify({"error": f"Could not remove language: {exc}"}), 500

    settings = current_app.user_settings
    settings.enabled_languages = [c for c in settings.enabled_languages if c != code]
    settings.save()

    return jsonify({"removed": code, "enabled_languages": settings.enabled_languages})


@bp.route("/settings/languages/enabled", methods=["POST"])
def set_language_enabled():
    """Enable or disable a language for detection. Applies straight away.

    Enabling loads the model now in eager mode (lazy mode loads it on first
    use), disabling drops it from RAM.

    Body: {"code": "nl", "enabled": true}
    """
    data = request.get_json(force=True, silent=True) or {}
    code = str(data.get("code", ""))
    enabled = bool(data.get("enabled", False))

    registry = current_app.language_registry
    if registry.info(code) is None:
        return jsonify({"error": f"Unsupported language: {code!r}"}), 400
    if enabled and not registry.is_installed(code):
        return jsonify({"error": "Install this language before enabling it."}), 400

    settings = current_app.user_settings
    current = settings.enabled_languages
    if enabled and code not in current:
        current.append(code)
    elif not enabled and code in current:
        current.remove(code)
    settings.enabled_languages = current
    settings.save()

    if not enabled:
        registry.unload(code)
    elif settings.loading_strategy == "eager":
        try:
            registry.ensure_loaded(code)
        except Exception as exc:
            return jsonify({"error": f"Could not load language: {exc}"}), 500

    return jsonify({"enabled_languages": settings.enabled_languages})


@bp.route("/settings/languages/loading-strategy", methods=["POST"])
def update_loading_strategy():
    """Update the loading strategy: 'eager' (all enabled languages at startup) or 'lazy'.

    Body: {"strategy": "eager"}
    Switching to eager loads every enabled language now. Switching to lazy
    keeps what is loaded; nothing more loads until a run needs it.
    """
    data = request.get_json(force=True, silent=True) or {}
    strategy = str(data.get("strategy", ""))

    settings = current_app.user_settings
    try:
        settings.loading_strategy = strategy
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    settings.save()

    if settings.loading_strategy == "eager":
        registry = current_app.language_registry
        try:
            for code in registry.usable_languages(settings.enabled_languages):
                registry.ensure_loaded(code)
        except Exception as exc:
            return jsonify({"error": f"Could not load language: {exc}"}), 500

    return jsonify({"loading_strategy": settings.loading_strategy})


@bp.route("/settings/hashing", methods=["POST"])
def set_hashing():
    """Enable or disable hashed placeholders and store the secret.

    Hashing is a single global choice rather than a per-mode one. The secret is
    what makes a placeholder stable: the same value under the same secret always
    encodes to the same token, so a subject keeps one identity across documents,
    across modes and across sessions. Setting it per mode would have broken that
    the moment two modes disagreed.

    Body: {"enabled": true, "secret": "..."}
    Returns {"enabled": bool, "secret": str} or {"error": str} with 400.
    """
    data = request.get_json(force=True, silent=True) or {}
    enabled = bool(data.get("enabled", False))
    settings = current_app.user_settings
    secret = str(data.get("secret", settings.hashing_secret))

    if enabled and not secret.strip():
        return jsonify({"error": "Enter a secret phrase to use hashing."}), 400

    settings.hashing_enabled = enabled
    # Kept even when hashing is switched off, so turning it back on later
    # reproduces the same placeholders rather than a fresh, unrelated set.
    if secret.strip():
        settings.hashing_secret = secret
    settings.save()

    return jsonify({
        "enabled": settings.hashing_enabled,
        "secret": settings.hashing_secret,
    })


@bp.route("/settings/detection", methods=["POST"])
def set_detection():
    """Update what counts as PII: dates, locations, URLs, numeric IDs, file names.

    These describe the user's definition of an identifying value, which cannot
    sensibly differ between pasting text, processing a folder, and serving an AI
    agent. They are therefore stored once here and read by every mode, rather
    than being posted with each run.

    Body: any subset of {"anonymize_dates": bool, "anonymize_locations": bool,
    "anonymize_urls": bool, "numeric_id_enabled": bool, "digit_count": int,
    "check_file_names": bool}
    """
    data = request.get_json(force=True, silent=True) or {}
    settings = current_app.user_settings
    config = settings.pattern_config

    if "anonymize_dates" in data:
        settings.anonymize_dates = bool(data["anonymize_dates"])
    if "anonymize_locations" in data:
        settings.anonymize_locations = bool(data["anonymize_locations"])
    if "anonymize_urls" in data:
        settings.anonymize_urls = bool(data["anonymize_urls"])
    if "numeric_id_enabled" in data:
        config.numeric_id_enabled = bool(data["numeric_id_enabled"])
    if "check_file_names" in data:
        config.check_file_names = bool(data["check_file_names"])
    if "digit_count" in data:
        try:
            config.digit_count = int(data["digit_count"])
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    settings.pattern_config = config
    settings.save()

    return jsonify({
        "anonymize_dates": settings.anonymize_dates,
        "anonymize_locations": settings.anonymize_locations,
        "anonymize_urls": settings.anonymize_urls,
        "numeric_id_enabled": settings.pattern_config.numeric_id_enabled,
        "digit_count": settings.pattern_config.digit_count,
        "check_file_names": settings.pattern_config.check_file_names,
    })


@bp.route("/settings/excel", methods=["POST"])
def set_excel():
    """Update Excel handling: generic NER on string cells, and by-column overrides.

    Body: any subset of {"excel_generic_enabled": bool, "excel_column_names": "a, b"}
    """
    data = request.get_json(force=True, silent=True) or {}
    settings = current_app.user_settings

    if "excel_generic_enabled" in data:
        settings.excel_generic_enabled = bool(data["excel_generic_enabled"])
    if "excel_column_names" in data:
        raw = str(data["excel_column_names"])
        settings.excel_column_names = [c.strip() for c in raw.split(",") if c.strip()]

    settings.save()
    return jsonify({
        "excel_generic_enabled": settings.excel_generic_enabled,
        "excel_column_names": ", ".join(settings.excel_column_names),
    })


@bp.route("/settings/folder-output", methods=["POST"])
def set_folder_output():
    """Update where folder-mode output goes and which extensions bypass scanning.

    Body: any subset of {"output_mode": "prefix"|"subfolder",
    "pass_through_extensions": ".sql, .mp4"}
    """
    data = request.get_json(force=True, silent=True) or {}
    settings = current_app.user_settings

    if "output_mode" in data:
        try:
            settings.output_mode = str(data["output_mode"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    if "pass_through_extensions" in data:
        settings.pass_through_extensions = normalize_extensions(
            str(data["pass_through_extensions"])
        )

    settings.save()
    return jsonify({
        "output_mode": settings.output_mode,
        "pass_through_extensions": ", ".join(settings.pass_through_extensions),
    })


@bp.route("/settings/default-language", methods=["POST"])
def set_default_language():
    """Set the language each mode starts on. Modes may still override per run.

    Body: {"language": "en"|"nl"}
    """
    data = request.get_json(force=True, silent=True) or {}
    settings = current_app.user_settings
    try:
        settings.language = str(data.get("language", ""))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    settings.save()
    return jsonify({"language": settings.language})


@bp.route("/settings/ai-mode", methods=["POST"])
def set_ai_mode():
    """Enable or disable AI Mode. Enabling for the first time lazily generates a token.

    Body: {"enabled": true}
    Returns {"enabled": bool, "token": str}.
    """
    data = request.get_json(force=True, silent=True) or {}
    enabled = bool(data.get("enabled", False))

    settings = current_app.user_settings
    settings.ai_mode_enabled = enabled
    settings.save()
    current_app.ai_session_store.set_timeout_minutes(settings.ai_session_timeout_minutes)

    return jsonify({"enabled": settings.ai_mode_enabled, "token": settings.ai_api_token})


@bp.route("/settings/ai-mode/regenerate-token", methods=["POST"])
def regenerate_ai_token():
    """Generate a new AI Mode API token, invalidating the previous one."""
    settings = current_app.user_settings
    token = settings.regenerate_ai_api_token()
    settings.save()
    return jsonify({"token": token})


@bp.route("/settings/ai-mode/config", methods=["POST"])
def update_ai_mode_config():
    """Update AI Mode's session timeout, temp folder, and inline text limit.

    Body: {"session_timeout_minutes": 60, "temp_dir": "C:/temp/d-tach-ai", "inline_text_max_chars": 50000}
    Each field is optional; only the fields provided are validated and applied.
    The temp folder is validated writable before being saved.
    """
    data = request.get_json(force=True, silent=True) or {}
    settings = current_app.user_settings

    if "session_timeout_minutes" in data:
        try:
            settings.ai_session_timeout_minutes = int(data["session_timeout_minutes"])
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400
        current_app.ai_session_store.set_timeout_minutes(settings.ai_session_timeout_minutes)

    if "inline_text_max_chars" in data:
        try:
            settings.ai_inline_text_max_chars = int(data["inline_text_max_chars"])
        except (TypeError, ValueError) as exc:
            return jsonify({"error": str(exc)}), 400

    if "temp_dir" in data:
        temp_dir = Path(str(data["temp_dir"]).strip())
        try:
            temp_dir.mkdir(parents=True, exist_ok=True)
            probe = temp_dir / ".d-tach-write-test"
            probe.write_text("", encoding="utf-8")
            probe.unlink()
        except OSError as exc:
            return jsonify({"error": f"Temp folder is not writable: {exc}"}), 400
        settings.ai_temp_dir = str(temp_dir)

    settings.save()
    return jsonify({
        "ai_session_timeout_minutes": settings.ai_session_timeout_minutes,
        "ai_inline_text_max_chars": settings.ai_inline_text_max_chars,
        "ai_temp_dir": settings.ai_temp_dir,
    })


def _build_ai_instructions(port: int, token: str) -> str:
    """Return the baseline AI-agent operating instructions for AI Mode, with port/token filled in."""
    return (
        f"AI Mode is enabled on d-tach (http://localhost:{port}). Before pointing me at a "
        "folder, run Document Mode's 'Rename names only' pass on it once so every path is "
        "already name-anonymized. From then on: normal directory listing of that folder is "
        "safe, but never read a file's contents directly — always call POST /ai/extract "
        "with the file path first and work only with the returned anonymized_text. Refer to "
        "the subject of each file only by its placeholder/hash, never a name you weren't given. "
        "When producing final output that needs real values restored, call POST /ai/restore "
        "with an output_path so the restored text is written straight to disk — never ask "
        "for it inline. Pass the session_id from /ai/extract, a keyref_path pointing at a "
        "KEYREF_*.csv, or both (the session wins on conflict). Use keyref_path when composing "
        "one output from several documents, or when the session has expired. "
        f"Include header X-D-Tach-Token: {token} on every request."
    )
