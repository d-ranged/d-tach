import json
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template, request

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
    """Process a single DOCX or PDF file at the given path.

    Expects JSON body:
        file_path             (str)
        language              (str)  — 'en' or 'nl'
        hashing_enabled       (bool)
        secret                (str)
        key_reference_enabled (bool)
        check_file_names      (bool)
        anonymize_dates       (bool)
    """
    data = request.get_json(force=True, silent=True) or {}
    processing_settings, error = _build_processing_settings(data)
    if error:
        return jsonify({"error": error}), 400

    file_path_str: str = data.get("file_path", "").strip()
    if not file_path_str:
        return jsonify({"error": "No file path provided."}), 400

    file_path = Path(file_path_str)
    if not file_path.exists():
        return jsonify({"error": f"File not found: {file_path_str}"}), 404
    if not file_path.is_file():
        return jsonify({"error": f"Path is not a file: {file_path_str}"}), 400

    result = current_app.file_processor.process(file_path, processing_settings)
    _persist_settings(data)

    return jsonify({
        "status": result.status,
        "output_path": str(result.output_path) if result.output_path else None,
        "keyref_path": str(result.keyref_path) if result.keyref_path else None,
        "entities_found": result.entities_found,
        "error_message": result.error_message,
    })


@bp.route("/document/process-folder", methods=["GET"])
def process_folder():
    """Process all supported files in a folder, streaming progress via SSE.

    Query parameters mirror the JSON body of process-file:
        folder_path, language, hashing_enabled, secret,
        key_reference_enabled, check_file_names, anonymize_dates

    Streams Server-Sent Events. Each event is a JSON object:
        type: "progress"  — one file completed
            n, total, status, file_name, output_path, entities_found, error_message
        type: "summary"   — all files done
            total, anonymized, clean, skipped, errors
        type: "error"     — folder-level validation failure
            message
    """
    args = request.args

    folder_path_str = args.get("folder_path", "").strip()
    hashing_enabled = args.get("hashing_enabled", "false").lower() == "true"
    secret = args.get("secret", "")
    key_reference_enabled = args.get("key_reference_enabled", "false").lower() == "true"
    check_file_names = args.get("check_file_names", "false").lower() == "true"
    anonymize_dates = args.get("anonymize_dates", "false").lower() == "true"
    language = args.get("language", "en")

    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    # Capture app-level objects now, while the application context is active.
    # The stream() generator runs lazily after the request context ends, so
    # accessing current_app inside the generator raises RuntimeError.
    folder_processor = current_app.folder_processor
    user_settings = current_app.user_settings

    def stream():
        if not folder_path_str:
            yield _sse({"type": "error", "message": "No folder path provided."})
            return

        if hashing_enabled and not secret.strip():
            yield _sse({"type": "error", "message": "Enter a secret phrase to use hashing."})
            return

        folder = Path(folder_path_str)
        if not folder.exists():
            yield _sse({"type": "error", "message": f"Folder not found: {folder_path_str}"})
            return
        if not folder.is_dir():
            yield _sse({"type": "error", "message": f"Path is not a folder: {folder_path_str}"})
            return

        processing_settings = ProcessingSettings(
            hashing_enabled=hashing_enabled,
            secret=secret,
            key_reference_enabled=key_reference_enabled,
            check_file_names=check_file_names,
            language=language,
            anonymize_dates=anonymize_dates,
        )

        all_results = []
        for result, n, total in folder_processor.process(
            folder, processing_settings
        ):
            all_results.append(result)
            yield _sse({
                "type": "progress",
                "n": n,
                "total": total,
                "status": result.status,
                "file_name": result.source_path.name,
                "output_path": str(result.output_path) if result.output_path else None,
                "entities_found": result.entities_found,
                "error_message": result.error_message,
            })

        summary = folder_processor.summarise(all_results)
        yield _sse({
            "type": "summary",
            "total": summary.total,
            "anonymized": summary.anonymized,
            "clean": summary.clean,
            "skipped": summary.skipped,
            "errors": summary.errors,
        })

        # Persist settings after successful run
        user_settings.language = language
        user_settings.hashing_enabled = hashing_enabled
        user_settings.anonymize_dates = anonymize_dates
        if hashing_enabled and secret.strip():
            user_settings.hashing_secret = secret
        user_settings.save()

    return Response(stream(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_processing_settings(data: dict) -> tuple[ProcessingSettings, str]:
    """Build ProcessingSettings from a request data dict; return (settings, error)."""
    hashing_enabled = bool(data.get("hashing_enabled", False))
    secret = data.get("secret", "")
    language = data.get("language", "en")

    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    if hashing_enabled and not secret.strip():
        return ProcessingSettings(), "Enter a secret phrase to use hashing."

    return ProcessingSettings(
        hashing_enabled=hashing_enabled,
        secret=secret,
        key_reference_enabled=bool(data.get("key_reference_enabled", False)),
        check_file_names=bool(data.get("check_file_names", False)),
        language=language,
        anonymize_dates=bool(data.get("anonymize_dates", False)),
    ), ""


def _persist_settings(data: dict) -> None:
    """Save language, hashing, and date settings from a request to UserSettings."""
    user_settings = current_app.user_settings
    language = data.get("language", "en")
    if language in _SUPPORTED_LANGUAGES:
        user_settings.language = language
    user_settings.hashing_enabled = bool(data.get("hashing_enabled", False))
    user_settings.anonymize_dates = bool(data.get("anonymize_dates", False))
    secret = data.get("secret", "")
    if data.get("hashing_enabled") and secret.strip():
        user_settings.hashing_secret = secret
    user_settings.save()


def _sse(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"
