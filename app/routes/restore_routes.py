from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

bp = Blueprint("restore", __name__)

_RESTORABLE_EXTENSIONS = frozenset({".docx", ".xlsx", ".md", ".txt"})


@bp.route("/restore")
def restore_mode():
    """Render the Restore tab."""
    settings = current_app.user_settings
    return render_template(
        "restore_mode.html",
        active_mode="restore",
        restore_input_path=settings.restore_input_path,
        restore_keyref_path=settings.restore_keyref_path,
    )


@bp.route("/restore/run", methods=["POST"])
def restore_run():
    """Restore an anonymized file using a KEYREF CSV.

    Expects JSON body:
        input_path   (str) — path to the anonymized file
        keyref_path  (str) — path to the KEYREF .csv file

    Returns JSON:
        status            — "restored" on success
        output_path       — path of the RESTORED_ output file
        replacements_made — number of placeholder replacements applied
        error             — present only on validation or processing error
    """
    data = request.get_json(force=True, silent=True) or {}
    input_path_str = data.get("input_path", "").strip()
    keyref_path_str = data.get("keyref_path", "").strip()

    if not input_path_str:
        return jsonify({"error": "No input file path provided."}), 400
    if not keyref_path_str:
        return jsonify({"error": "No KEYREF file path provided."}), 400

    input_path = Path(input_path_str)
    keyref_path = Path(keyref_path_str)

    if not input_path.exists():
        return jsonify({"error": f"File not found: {input_path_str}"}), 404
    if not input_path.is_file():
        return jsonify({"error": f"Path is not a file: {input_path_str}"}), 400
    if not keyref_path.exists():
        return jsonify({"error": f"KEYREF file not found: {keyref_path_str}"}), 404

    if input_path.suffix.lower() not in _RESTORABLE_EXTENSIONS:
        return jsonify({
            "error": f"Unsupported file type: {input_path.suffix}. Supported: DOCX, XLSX, MD, TXT."
        }), 400

    result = current_app.file_processor.restore_file(input_path, keyref_path)

    if result.status == "error":
        return jsonify({"error": result.error_message}), 400

    # Persist last-used paths
    settings = current_app.user_settings
    settings.restore_input_path = input_path_str
    settings.restore_keyref_path = keyref_path_str
    settings.save()

    return jsonify({
        "status": result.status,
        "output_path": str(result.output_path) if result.output_path else None,
        "replacements_made": result.entities_found,
    })
