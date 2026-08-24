import logging
from pathlib import Path
from typing import Optional

from flask import Blueprint, Response, current_app, jsonify, request

from app.services.document_processor import DocumentProcessor
from app.services.file_processor import ProcessingSettings

logger = logging.getLogger(__name__)

bp = Blueprint("ai", __name__, url_prefix="/ai")

_SUPPORTED_LANGUAGES = ("en", "nl")
_TOKEN_HEADER = "X-D-Tach-Token"


@bp.before_request
def _guard() -> Optional[Response]:
    """Gate every /ai/* route: 404 when AI Mode is off, 401 on a missing/wrong token.

    404 (not 403) when disabled so a probing request cannot even confirm the
    route exists.
    """
    settings = current_app.user_settings
    if not settings.ai_mode_enabled:
        return jsonify({"error": "Not found."}), 404
    token = request.headers.get(_TOKEN_HEADER, "")
    if not token or token != settings.ai_api_token:
        return jsonify({"error": "Missing or invalid X-D-Tach-Token header."}), 401
    return None


@bp.route("/status", methods=["GET"])
def status():
    """Confirm AI Mode is enabled and the caller's token is valid."""
    return jsonify({"enabled": True})


@bp.route("/extract", methods=["POST"])
def extract():
    """Extract and anonymize a file's text without writing anything to disk.

    Body mirrors /document/process-file's settings (file_path required; all
    others optional and fall back to the saved UserSettings). Returns the
    anonymized text inline, or a path to a temp file when the result exceeds
    ai_inline_text_max_chars.
    """
    data = request.get_json(force=True, silent=True) or {}
    file_path_str = str(data.get("file_path", "")).strip()
    if not file_path_str:
        return jsonify({"error": "No file path provided."}), 400

    file_path = Path(file_path_str)
    if not file_path.exists():
        return jsonify({"error": f"File not found: {file_path_str}"}), 404
    if not file_path.is_file():
        return jsonify({"error": f"Path is not a file: {file_path_str}"}), 400

    user_settings = current_app.user_settings
    processing_settings, error = _build_ai_processing_settings(data, user_settings)
    if error:
        return jsonify({"error": error}), 400

    result = current_app.file_processor.extract_anonymized_text(file_path, processing_settings)
    if result.status == "error":
        return jsonify({"error": result.error_message}), 500
    if result.status == "skipped":
        return jsonify({"error": result.error_message}), 400
    if result.status == "unreadable":
        return jsonify({"error": result.error_message, "warnings": result.warnings}), 422

    placeholder_to_original = {placeholder: original for original, placeholder in result.replacements.items()}
    session_id = current_app.ai_session_store.create(placeholder_to_original, file_path)

    response = {
        "session_id": session_id,
        "entities": [
            {"type": e.entity_type, "placeholder": e.placeholder} for e in result.entities
        ],
        "warnings": result.warnings,
    }
    response.update(_inline_or_temp_file(
        result.anonymized_text, session_id, "extracted", "anonymized_text", user_settings,
    ))
    return jsonify(response)


@bp.route("/restore", methods=["POST"])
def restore():
    """Substitute placeholders back to real values for a given session.

    Accepts inline `text` or a `text_path` to read from. With `output_path`,
    writes the restored text directly to disk and the response carries no
    restored content — only status and path. Without it, returns the restored
    text inline or via a temp-file path, using the same threshold as /ai/extract.
    """
    data = request.get_json(force=True, silent=True) or {}
    session_id = str(data.get("session_id", "")).strip()
    if not session_id:
        return jsonify({"error": "session_id is required."}), 400

    session = current_app.ai_session_store.get(session_id)
    if session is None:
        return jsonify({"error": "Unknown or expired session_id."}), 404

    text = data.get("text")
    text_path_str = str(data.get("text_path", "")).strip()
    if text is None and not text_path_str:
        return jsonify({"error": "Provide either text or text_path."}), 400
    if text is None:
        text_path = Path(text_path_str)
        if not text_path.is_file():
            return jsonify({"error": f"text_path not found: {text_path_str}"}), 404
        text = text_path.read_text(encoding="utf-8")

    restored_text, replacements_applied = DocumentProcessor.restore_string(text, session.replacements)

    output_path_str = str(data.get("output_path", "")).strip()
    if output_path_str:
        output_path = Path(output_path_str)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(restored_text, encoding="utf-8")
        return jsonify({
            "status": "written",
            "output_path": str(output_path),
            "replacements_applied": replacements_applied,
        })

    user_settings = current_app.user_settings
    response = {"replacements_applied": replacements_applied}
    response.update(_inline_or_temp_file(
        restored_text, session_id, "restored", "restored_text", user_settings,
    ))
    return jsonify(response)


@bp.route("/flag-term", methods=["POST"])
def flag_term():
    """Add a value to UserSettings.known_values so future extractions catch it.

    Body: {"value": "Missed Name", "entity_type": "PERSON"} — entity_type optional.
    """
    data = request.get_json(force=True, silent=True) or {}
    value = str(data.get("value", "")).strip()
    if not value:
        return jsonify({"error": "value is required."}), 400
    entity_type = str(data.get("entity_type") or "PERSON")

    user_settings = current_app.user_settings
    current = user_settings.known_values
    if not any(v["value"].lower() == value.lower() for v in current):
        current.append({"value": value, "entity_type": entity_type, "source": "manual"})
        user_settings.known_values = current
        user_settings.save()

    return jsonify({"status": "added", "known_values": user_settings.known_values})


def _build_ai_processing_settings(data: dict, user_settings) -> tuple[ProcessingSettings, str]:
    """Build ProcessingSettings for /ai/extract from a request body, falling back to saved settings."""
    hashing_enabled = bool(data.get("hashing_enabled", user_settings.hashing_enabled))
    secret = str(data.get("secret", user_settings.hashing_secret))
    if hashing_enabled and not secret.strip():
        return ProcessingSettings(), "Enter a secret phrase to use hashing."

    language = data.get("language", user_settings.language)
    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    raw_columns = data.get("excel_column_names", user_settings.excel_column_names)
    if isinstance(raw_columns, str):
        excel_column_names = [c.strip() for c in raw_columns.split(",") if c.strip()]
    else:
        excel_column_names = [str(c) for c in raw_columns]

    pattern_config = user_settings.pattern_config
    settings = ProcessingSettings(
        hashing_enabled=hashing_enabled,
        secret=secret,
        language=language,
        anonymize_dates=bool(data.get("anonymize_dates", user_settings.anonymize_dates)),
        anonymize_locations=bool(data.get("anonymize_locations", user_settings.anonymize_locations)),
        anonymize_urls=bool(data.get("anonymize_urls", user_settings.anonymize_urls)),
        numeric_id_enabled=bool(data.get("numeric_id_enabled", pattern_config.numeric_id_enabled)),
        digit_count=int(data.get("digit_count", pattern_config.digit_count)),
        excel_generic_enabled=bool(data.get("excel_generic_enabled", user_settings.excel_generic_enabled)),
        excel_column_names=excel_column_names,
        known_values=user_settings.known_values,
        loading_strategy=user_settings.loading_strategy,
    )
    return settings, ""


def _write_temp_text(text: str, session_id: str, suffix: str, user_settings) -> Path:
    """Write text to a session-named temp file under ai_temp_dir; return its path."""
    temp_dir = Path(user_settings.ai_temp_dir)
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / f"{session_id}_{suffix}.txt"
    temp_path.write_text(text, encoding="utf-8")
    return temp_path


def _inline_or_temp_file(
    text: str, session_id: str, suffix: str, field_base: str, user_settings,
) -> dict:
    """Return {field_base: text} when under the inline threshold, else {field_base_path: path}.

    Large results are written to ai_temp_dir instead of inlined, so a big
    extraction or restoration does not flood the AI agent's context window.
    """
    if len(text) <= user_settings.ai_inline_text_max_chars:
        return {field_base: text}
    temp_path = _write_temp_text(text, session_id, suffix, user_settings)
    current_app.ai_session_store.add_temp_file(session_id, temp_path)
    return {f"{field_base}_path": str(temp_path)}
