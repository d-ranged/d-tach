from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

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

    Body: {"file_path": "C:/roster.xlsx", "column_mapping": {"Name": "PERSON"}}
    Merges new values into the existing known values list (deduped
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
    except Exception as exc:
        return jsonify({"error": f"Import failed: {exc}"}), 400

    settings.known_values = updated_values
    settings.class_list_path = str(file_path)
    settings.class_list_column_mapping = column_mapping
    settings.save()

    return jsonify({
        "added": result.added,
        "already_present": result.already_present,
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
    """Uninstall a language's spaCy model and disable it.

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
    """Enable or disable a language for startup loading / detection.

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

    return jsonify({"enabled_languages": settings.enabled_languages})


@bp.route("/settings/languages/loading-strategy", methods=["POST"])
def update_loading_strategy():
    """Update the loading strategy: 'eager' (all enabled languages at startup) or 'lazy'.

    Body: {"strategy": "eager"}
    Takes effect after restart.
    """
    data = request.get_json(force=True, silent=True) or {}
    strategy = str(data.get("strategy", ""))

    settings = current_app.user_settings
    try:
        settings.loading_strategy = strategy
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    settings.save()

    return jsonify({"loading_strategy": settings.loading_strategy})
