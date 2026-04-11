from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from app.services.file_processor import ProcessingSettings

bp = Blueprint("document", __name__)

_SUPPORTED_LANGUAGES = ("en", "nl")


@bp.route("/document")
def document_mode():
    """Render the Document Mode page."""
    settings = current_app.user_settings
    return render_template(
        "document_mode.html",
        active_mode="document",
        language=settings.language,
        hashing_enabled=settings.hashing_enabled,
        hashing_secret=settings.hashing_secret,
        anonymize_dates=settings.anonymize_dates,
        pattern_config=settings.pattern_config,
    )


@bp.route("/document/process-file", methods=["POST"])
def process_file():
    """Process a single DOCX file at the given path and return the result as JSON.

    Expects JSON body:
        file_path             (str)  — absolute path to the DOCX file
        language              (str)  — 'en' or 'nl', user-selected
        hashing_enabled       (bool)
        secret                (str)  — required when hashing_enabled is true
        key_reference_enabled (bool)
        check_file_names      (bool)
        anonymize_dates       (bool) — include DATE_TIME entities; default false

    Returns JSON:
        status          (str)
        output_path     (str | null)
        keyref_path     (str | null)
        entities_found  (int)
        error_message   (str | null)
    """
    data = request.get_json(force=True, silent=True) or {}
    file_path_str: str = data.get("file_path", "").strip()
    language: str = data.get("language", "en")
    hashing_enabled: bool = bool(data.get("hashing_enabled", False))
    secret: str = data.get("secret", "")
    key_reference_enabled: bool = bool(data.get("key_reference_enabled", False))
    check_file_names: bool = bool(data.get("check_file_names", False))
    anonymize_dates: bool = bool(data.get("anonymize_dates", False))

    if not file_path_str:
        return jsonify({"error": "No file path provided."}), 400

    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    if hashing_enabled and not secret.strip():
        return jsonify({"error": "Enter a secret phrase to use hashing."}), 400

    file_path = Path(file_path_str)
    if not file_path.exists():
        return jsonify({"error": f"File not found: {file_path_str}"}), 404
    if not file_path.is_file():
        return jsonify({"error": f"Path is not a file: {file_path_str}"}), 400

    processing_settings = ProcessingSettings(
        hashing_enabled=hashing_enabled,
        secret=secret,
        key_reference_enabled=key_reference_enabled,
        check_file_names=check_file_names,
        language=language,
        anonymize_dates=anonymize_dates,
    )

    result = current_app.file_processor.process(file_path, processing_settings)

    user_settings = current_app.user_settings
    user_settings.language = language
    user_settings.hashing_enabled = hashing_enabled
    user_settings.anonymize_dates = anonymize_dates
    if hashing_enabled and secret.strip():
        user_settings.hashing_secret = secret
    user_settings.save()

    return jsonify({
        "status": result.status,
        "output_path": str(result.output_path) if result.output_path else None,
        "keyref_path": str(result.keyref_path) if result.keyref_path else None,
        "entities_found": result.entities_found,
        "error_message": result.error_message,
    })
