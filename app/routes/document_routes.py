import json
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from app.services.file_processor import ProcessingSettings
from app.services.folder_processor import normalize_extensions

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
        anonymize_locations=settings.anonymize_locations,
        anonymize_urls=settings.anonymize_urls,
        pattern_config=settings.pattern_config,
        excel_generic_enabled=settings.excel_generic_enabled,
        excel_column_names=", ".join(settings.excel_column_names),
        output_mode=settings.output_mode,
        pass_through_extensions=", ".join(settings.pass_through_extensions),
    )


@bp.route("/document/process-file", methods=["POST"])
def process_file():
    """Process a single DOCX or PDF file at the given path.

    Expects JSON body:
        file_path                (str)
        language                 (str)  — 'en' or 'nl'
        hashing_enabled          (bool)
        secret                   (str)
        key_reference_enabled    (bool)
        check_file_names         (bool)
        anonymize_dates          (bool)
        numeric_id_enabled   (bool)
        digit_count              (int)
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
        "warnings": result.warnings,
    })


@bp.route("/document/process-folder", methods=["GET"])
def process_folder():
    """Process all supported files in a folder, streaming progress via SSE.

    Query parameters mirror the JSON body of process-file:
        folder_path, language, hashing_enabled, secret,
        key_reference_enabled, check_file_names, anonymize_dates,
        numeric_id_enabled, digit_count

    Streams Server-Sent Events. Each event is a JSON object:
        type: "progress"  — one file completed
            n, total, status, file_name, output_path, entities_found, error_message
        type: "summary"   — all files done
            total, anonymized, clean, skipped, errors, copied
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
    anonymize_locations = args.get("anonymize_locations", "false").lower() == "true"
    anonymize_urls = args.get("anonymize_urls", "false").lower() == "true"
    numeric_id_enabled = args.get("numeric_id_enabled", "false").lower() == "true"
    digit_count_raw = args.get("digit_count", "7")
    try:
        digit_count = int(digit_count_raw)
    except (ValueError, TypeError):
        digit_count = 7
    language = args.get("language", "en")
    excel_generic_enabled = args.get("excel_generic_enabled", "true").lower() == "true"
    excel_column_names_raw = args.get("excel_column_names", "").strip()
    excel_column_names = [c.strip() for c in excel_column_names_raw.split(",") if c.strip()]
    output_mode = args.get("output_mode", "prefix")
    if output_mode not in ("prefix", "subfolder"):
        output_mode = "prefix"
    pass_through_extensions = normalize_extensions(args.get("pass_through_extensions", "").strip())

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
            anonymize_locations=anonymize_locations,
            anonymize_urls=anonymize_urls,
            numeric_id_enabled=numeric_id_enabled,
            digit_count=digit_count,
            excel_generic_enabled=excel_generic_enabled,
            excel_column_names=excel_column_names,
            output_mode=output_mode,
            known_values=user_settings.known_values,
            pass_through_extensions=pass_through_extensions,
            loading_strategy=user_settings.loading_strategy,
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
                "warnings": result.warnings,
            })

        summary = folder_processor.summarise(
            all_results,
            folder=folder,
            key_reference_enabled=key_reference_enabled,
            output_mode=output_mode,
        )
        yield _sse({
            "type": "summary",
            "total": summary.total,
            "anonymized": summary.anonymized,
            "clean": summary.clean,
            "unreadable": summary.unreadable,
            "skipped": summary.skipped,
            "errors": summary.errors,
            "copied": summary.copied,
            "keyref_csv_path": str(summary.keyref_csv_path) if summary.keyref_csv_path else None,
        })

        # Persist settings after successful run
        from app.services.pattern_config import PatternConfig
        user_settings.language = language
        user_settings.hashing_enabled = hashing_enabled
        user_settings.anonymize_dates = anonymize_dates
        user_settings.anonymize_locations = anonymize_locations
        user_settings.anonymize_urls = anonymize_urls
        if hashing_enabled and secret.strip():
            user_settings.hashing_secret = secret
        user_settings.pattern_config = PatternConfig(
            digit_count=digit_count,
            numeric_id_enabled=numeric_id_enabled,
            check_file_names=check_file_names,
        )
        user_settings.excel_generic_enabled = excel_generic_enabled
        user_settings.excel_column_names = excel_column_names
        user_settings.output_mode = output_mode
        user_settings.pass_through_extensions = pass_through_extensions
        user_settings.save()

    return Response(stream(), mimetype="text/event-stream",
                    headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"})


@bp.route("/document/rename-folder", methods=["GET"])
def rename_folder():
    """Rename every file and folder name under a folder in place, streaming progress via SSE.

    No file content is read or rewritten — only names change, and no
    anonymized/ output tree is created. This is the prerequisite step for
    pointing AI Mode at a real folder: it makes path enumeration safe before
    any content is read.

    Query parameters (narrower than process-folder — no excel/output_mode/
    pass_through settings apply to a names-only pass):
        folder_path, language, hashing_enabled, secret,
        key_reference_enabled, anonymize_dates, anonymize_locations,
        anonymize_urls, numeric_id_enabled, digit_count

    Streams the same event shapes as process-folder ("progress", "summary",
    "error").
    """
    args = request.args

    folder_path_str = args.get("folder_path", "").strip()
    hashing_enabled = args.get("hashing_enabled", "false").lower() == "true"
    secret = args.get("secret", "")
    key_reference_enabled = args.get("key_reference_enabled", "false").lower() == "true"
    anonymize_dates = args.get("anonymize_dates", "false").lower() == "true"
    anonymize_locations = args.get("anonymize_locations", "false").lower() == "true"
    anonymize_urls = args.get("anonymize_urls", "false").lower() == "true"
    numeric_id_enabled = args.get("numeric_id_enabled", "false").lower() == "true"
    expand_archives = args.get("expand_archives", "false").lower() == "true"
    delete_archives = args.get("delete_archives_after_expand", "false").lower() == "true"
    digit_count_raw = args.get("digit_count", "7")
    try:
        digit_count = int(digit_count_raw)
    except (ValueError, TypeError):
        digit_count = 7
    language = args.get("language", "en")
    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    # Capture app-level objects now, while the application context is active —
    # see the identical comment on process-folder above for why.
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
            language=language,
            anonymize_dates=anonymize_dates,
            anonymize_locations=anonymize_locations,
            anonymize_urls=anonymize_urls,
            numeric_id_enabled=numeric_id_enabled,
            digit_count=digit_count,
            known_values=user_settings.known_values,
            loading_strategy=user_settings.loading_strategy,
            expand_archives=expand_archives,
            delete_archives_after_expand=delete_archives,
        )

        # Archives are expanded first so that files which only existed inside one
        # are renamed and enumerable like everything else in the tree.
        for archive in folder_processor.expand_archives(folder, processing_settings):
            yield _sse({
                "type": "archive",
                "status": archive.status,
                "file_name": archive.source_path.name,
                "destination": archive.destination.name if archive.destination else "",
                "member_count": archive.member_count,
                "deleted_source": archive.deleted_source,
                "error_message": archive.error_message,
            })

        all_results = []
        for result, n, total in folder_processor.rename_in_place(folder, processing_settings):
            all_results.append(result)
            yield _sse({
                "type": "progress",
                "n": n,
                "total": total,
                "status": result.status,
                "file_name": result.source_path.name,
                "entities_found": result.entities_found,
                "error_message": result.error_message,
                "warnings": result.warnings,
            })

        summary = folder_processor.summarise(
            all_results,
            folder=folder,
            key_reference_enabled=key_reference_enabled,
            output_mode="prefix",
        )
        yield _sse({
            "type": "summary",
            "total": summary.total,
            "anonymized": summary.anonymized,
            "clean": summary.clean,
            "unreadable": summary.unreadable,
            "skipped": summary.skipped,
            "errors": summary.errors,
            "copied": summary.copied,
            "keyref_csv_path": str(summary.keyref_csv_path) if summary.keyref_csv_path else None,
        })

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

    try:
        digit_count = int(data.get("digit_count", 7))
    except (ValueError, TypeError):
        digit_count = 7

    excel_column_names_raw = data.get("excel_column_names", "").strip()
    excel_column_names = [c.strip() for c in excel_column_names_raw.split(",") if c.strip()]

    from flask import current_app
    known_values = current_app.user_settings.known_values
    loading_strategy = current_app.user_settings.loading_strategy

    return ProcessingSettings(
        hashing_enabled=hashing_enabled,
        secret=secret,
        key_reference_enabled=bool(data.get("key_reference_enabled", False)),
        check_file_names=bool(data.get("check_file_names", False)),
        language=language,
        anonymize_dates=bool(data.get("anonymize_dates", False)),
        anonymize_locations=bool(data.get("anonymize_locations", False)),
        anonymize_urls=bool(data.get("anonymize_urls", False)),
        numeric_id_enabled=bool(data.get("numeric_id_enabled", False)),
        digit_count=digit_count,
        excel_generic_enabled=bool(data.get("excel_generic_enabled", True)),
        excel_column_names=excel_column_names,
        known_values=known_values,
        loading_strategy=loading_strategy,
    ), ""


def _persist_settings(data: dict) -> None:
    """Save language, hashing, date, and pattern settings from a request to UserSettings."""
    from app.services.pattern_config import PatternConfig
    user_settings = current_app.user_settings
    language = data.get("language", "en")
    if language in _SUPPORTED_LANGUAGES:
        user_settings.language = language
    user_settings.hashing_enabled = bool(data.get("hashing_enabled", False))
    user_settings.anonymize_dates = bool(data.get("anonymize_dates", False))
    user_settings.anonymize_locations = bool(data.get("anonymize_locations", False))
    user_settings.anonymize_urls = bool(data.get("anonymize_urls", False))
    secret = data.get("secret", "")
    if data.get("hashing_enabled") and secret.strip():
        user_settings.hashing_secret = secret
    try:
        digit_count = int(data.get("digit_count", 7))
    except (ValueError, TypeError):
        digit_count = 7
    numeric_id_enabled = bool(data.get("numeric_id_enabled", False))
    user_settings.pattern_config = PatternConfig(
        digit_count=digit_count,
        numeric_id_enabled=numeric_id_enabled,
        check_file_names=bool(data.get("check_file_names", False)),
    )
    user_settings.excel_generic_enabled = bool(data.get("excel_generic_enabled", True))
    excel_col_raw = data.get("excel_column_names", "").strip()
    user_settings.excel_column_names = [c.strip() for c in excel_col_raw.split(",") if c.strip()]
    user_settings.save()


def _sse(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"
