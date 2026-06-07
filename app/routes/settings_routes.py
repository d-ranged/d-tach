from flask import Blueprint, current_app, jsonify, request

bp = Blueprint("settings", __name__)


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
