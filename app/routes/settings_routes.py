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
    """Return the current known values list."""
    return jsonify({"values": current_app.user_settings.known_values})


@bp.route("/settings/known-values", methods=["POST"])
def add_known_value():
    """Append a value to the known values list.

    Body: {"value": "Name to always anonymize"}
    Silently ignores duplicates (case-insensitive comparison).
    Returns the updated list.
    """
    data = request.get_json(force=True, silent=True) or {}
    value = str(data.get("value", "")).strip()
    if not value:
        return jsonify({"error": "Value cannot be empty."}), 400

    settings = current_app.user_settings
    current = settings.known_values
    if not any(v.lower() == value.lower() for v in current):
        current.append(value)
        settings.known_values = current
        settings.save()

    return jsonify({"values": settings.known_values})


@bp.route("/settings/known-values", methods=["DELETE"])
def remove_known_value():
    """Remove a value from the known values list (case-insensitive).

    Body: {"value": "Name to remove"}
    Returns the updated list.
    """
    data = request.get_json(force=True, silent=True) or {}
    value = str(data.get("value", "")).strip()

    settings = current_app.user_settings
    updated = [v for v in settings.known_values if v.lower() != value.lower()]
    settings.known_values = updated
    settings.save()

    return jsonify({"values": settings.known_values})


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
