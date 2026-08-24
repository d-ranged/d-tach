from flask import Blueprint, current_app, jsonify, render_template, request, url_for

bp = Blueprint("setup", __name__)


@bp.route("/setup")
def setup_page():
    """Render the first-launch language-selection screen."""
    registry = current_app.language_registry
    languages = [
        {
            "code": lang.code,
            "name": lang.name,
            "download_size_mb": lang.download_size_mb,
            "installed": registry.is_installed(lang.code),
        }
        for lang in registry.supported_languages()
    ]
    return render_template("language_setup.html", languages=languages)


@bp.route("/setup/install", methods=["POST"])
def start_setup_install():
    """Start background downloads for the selected languages not yet installed.

    Body: {"codes": ["en", "nl"]}
    """
    data = request.get_json(force=True, silent=True) or {}
    codes = data.get("codes", [])

    registry = current_app.language_registry
    for code in codes:
        if registry.info(code) is not None and not registry.is_installed(code):
            registry.start_download(code)

    return jsonify({"started": True})


@bp.route("/setup/status", methods=["GET"])
def setup_status():
    """Return install status for every requested language code.

    Query: ?codes=en,nl
    Returns {code: {"state": "idle"|"downloading"|"done"|"error", "message": str}}.
    """
    codes = [c for c in request.args.get("codes", "").split(",") if c]
    registry = current_app.language_registry

    statuses = {}
    for code in codes:
        if registry.is_installed(code):
            statuses[code] = {"state": "done", "message": ""}
        else:
            statuses[code] = registry.download_status(code)
    return jsonify(statuses)


@bp.route("/setup/complete", methods=["POST"])
def complete_setup():
    """Finalize first-launch setup: persist enabled languages, mark setup done.

    Body: {"codes": ["en", "nl"]}
    Only languages that finished installing are actually enabled; if none did,
    falls back to English alone (it is pre-selected and always offered first).
    """
    data = request.get_json(force=True, silent=True) or {}
    codes = data.get("codes", [])

    registry = current_app.language_registry
    installed_selected = [c for c in codes if registry.is_installed(c)]
    if not installed_selected and registry.is_installed("en"):
        installed_selected = ["en"]

    # Load the just-downloaded models into this running process now, so the
    # main app is immediately usable without requiring a restart.
    for code in installed_selected:
        current_app.anonymizer.ensure_loaded(code)

    settings = current_app.user_settings
    settings.enabled_languages = installed_selected
    settings.language_setup_complete = True
    settings.save()

    return jsonify({"redirect": url_for("text.text_mode")})
