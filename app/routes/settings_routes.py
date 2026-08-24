from flask import Blueprint, current_app, jsonify, render_template, request

from app.services.user_settings import MAX_PORT, MIN_PORT

bp = Blueprint("settings", __name__)


@bp.route("/settings")
def settings_page():
    """Render the Settings page."""
    settings = current_app.user_settings
    return render_template(
        "settings.html",
        active_mode="settings",
        port=settings.port,
        min_port=MIN_PORT,
        max_port=MAX_PORT,
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
