import json
from pathlib import Path

from flask import Blueprint, Response, current_app, jsonify, render_template, request

from app.routes import build_detection_summary
from app.services.file_processor import ProcessingSettings
from app.services.folder_processor import normalize_extensions
from app.services.language_registry import pick_language

bp = Blueprint("document", __name__)

_SUPPORTED_LANGUAGES = ("en", "nl")


@bp.route("/document")
def document_mode():
    """Render the Document Mode page."""
    settings = current_app.user_settings
    registry = current_app.language_registry
    return render_template(
        "document_mode.html",
        active_mode="document",
        language=pick_language(settings.language, registry.usable_languages(settings.enabled_languages)),
        detection_summary=build_detection_summary(settings, include_file_names=True),
        output_mode=settings.output_mode,
    )


@bp.route("/document/process-file", methods=["POST"])
def process_file():
    """Process a single DOCX or PDF file at the given path.

    Detection settings come from Settings and are shared by every mode; each may
    still be overridden per request by an API caller, but omitting one inherits
    the saved value.

    Expects JSON body:
        file_path                (str)
        language                 (str)  — 'en' or 'nl'; defaults to the saved language
        key_reference_enabled    (bool) — per-run; not saved
        hashing_enabled, secret, check_file_names, anonymize_dates,
        anonymize_locations, anonymize_urls, numeric_id_enabled, digit_count,
        excel_generic_enabled, excel_column_names — optional overrides
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

    Query parameters mirror the JSON body of process-file: folder_path plus the
    per-run choices (language, key_reference_enabled). Every detection setting
    falls back to the saved Settings value when the parameter is absent.

    Streams Server-Sent Events. Each event is a JSON object:
        type: "progress"  — one file completed
            n, total, status, file_name, output_path, entities_found, error_message
        type: "summary"   — all files done
            total, anonymized, clean, skipped, errors, copied
        type: "error"     — folder-level validation failure
            message
    """
    args = request.args
    saved = current_app.user_settings
    saved_config = saved.pattern_config

    folder_path_str = args.get("folder_path", "").strip()
    hashing_enabled = _arg_bool(args, "hashing_enabled", saved.hashing_enabled)
    secret = args.get("secret", saved.hashing_secret)
    key_reference_enabled = _arg_bool(args, "key_reference_enabled", False)
    check_file_names = _arg_bool(args, "check_file_names", saved_config.check_file_names)
    anonymize_dates = _arg_bool(args, "anonymize_dates", saved.anonymize_dates)
    anonymize_locations = _arg_bool(args, "anonymize_locations", saved.anonymize_locations)
    anonymize_urls = _arg_bool(args, "anonymize_urls", saved.anonymize_urls)
    numeric_id_enabled = _arg_bool(args, "numeric_id_enabled", saved_config.numeric_id_enabled)
    try:
        digit_count = int(args.get("digit_count", saved_config.digit_count))
    except (ValueError, TypeError):
        digit_count = saved_config.digit_count
    language = args.get("language", saved.language)
    excel_generic_enabled = _arg_bool(
        args, "excel_generic_enabled", saved.excel_generic_enabled
    )
    if "excel_column_names" in args:
        excel_column_names = [
            c.strip() for c in args["excel_column_names"].split(",") if c.strip()
        ]
    else:
        excel_column_names = saved.excel_column_names
    output_mode = args.get("output_mode", saved.output_mode)
    if output_mode not in ("prefix", "subfolder"):
        output_mode = saved.output_mode
    if "pass_through_extensions" in args:
        pass_through_extensions = normalize_extensions(args["pass_through_extensions"].strip())
    else:
        pass_through_extensions = saved.pass_through_extensions

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
    pass_through settings apply to a names-only pass): folder_path, the archive
    flags, and the per-run choices. Detection settings fall back to Settings.

    Streams the same event shapes as process-folder ("progress", "summary",
    "error").
    """
    args = request.args
    saved = current_app.user_settings
    saved_config = saved.pattern_config

    folder_path_str = args.get("folder_path", "").strip()
    hashing_enabled = _arg_bool(args, "hashing_enabled", saved.hashing_enabled)
    secret = args.get("secret", saved.hashing_secret)
    key_reference_enabled = _arg_bool(args, "key_reference_enabled", False)
    anonymize_dates = _arg_bool(args, "anonymize_dates", saved.anonymize_dates)
    anonymize_locations = _arg_bool(args, "anonymize_locations", saved.anonymize_locations)
    anonymize_urls = _arg_bool(args, "anonymize_urls", saved.anonymize_urls)
    numeric_id_enabled = _arg_bool(args, "numeric_id_enabled", saved_config.numeric_id_enabled)
    expand_archives = _arg_bool(args, "expand_archives", False)
    delete_archives = _arg_bool(args, "delete_archives_after_expand", False)
    try:
        digit_count = int(args.get("digit_count", saved_config.digit_count))
    except (ValueError, TypeError):
        digit_count = saved_config.digit_count
    language = args.get("language", saved.language)
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

def _arg_bool(args, name: str, default: bool) -> bool:
    """Read a "true"/"false" query parameter, falling back to a saved default.

    An absent parameter means "use what is configured", not False. The earlier
    version defaulted every detection flag off, so any caller that omitted one
    silently ran with that detection disabled.
    """
    raw = args.get(name)
    if raw is None:
        return default
    return raw.lower() == "true"


def _build_processing_settings(data: dict) -> tuple[ProcessingSettings, str]:
    """Build ProcessingSettings from a request data dict; return (settings, error).

    Detection settings default to the saved Settings values. A request may
    override any of them for that one run, but never writes back.
    """
    saved = current_app.user_settings
    saved_config = saved.pattern_config

    hashing_enabled = bool(data.get("hashing_enabled", saved.hashing_enabled))
    secret = data.get("secret", saved.hashing_secret)
    language = data.get("language", saved.language)

    if language not in _SUPPORTED_LANGUAGES:
        language = "en"

    if hashing_enabled and not secret.strip():
        return ProcessingSettings(), "Enter a secret phrase to use hashing."

    try:
        digit_count = int(data.get("digit_count", saved_config.digit_count))
    except (ValueError, TypeError):
        digit_count = saved_config.digit_count

    if "excel_column_names" in data:
        raw = str(data["excel_column_names"])
        excel_column_names = [c.strip() for c in raw.split(",") if c.strip()]
    else:
        excel_column_names = saved.excel_column_names

    return ProcessingSettings(
        hashing_enabled=hashing_enabled,
        secret=secret,
        key_reference_enabled=bool(data.get("key_reference_enabled", False)),
        check_file_names=bool(
            data.get("check_file_names", saved_config.check_file_names)
        ),
        language=language,
        anonymize_dates=bool(data.get("anonymize_dates", saved.anonymize_dates)),
        anonymize_locations=bool(
            data.get("anonymize_locations", saved.anonymize_locations)
        ),
        anonymize_urls=bool(data.get("anonymize_urls", saved.anonymize_urls)),
        numeric_id_enabled=bool(
            data.get("numeric_id_enabled", saved_config.numeric_id_enabled)
        ),
        digit_count=digit_count,
        excel_generic_enabled=bool(
            data.get("excel_generic_enabled", saved.excel_generic_enabled)
        ),
        excel_column_names=excel_column_names,
        known_values=saved.known_values,
        loading_strategy=saved.loading_strategy,
    ), ""


def _sse(data: dict) -> str:
    """Format a dict as a Server-Sent Event string."""
    return f"data: {json.dumps(data)}\n\n"
