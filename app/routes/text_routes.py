from flask import Blueprint, render_template

bp = Blueprint("text", __name__)


@bp.route("/")
def index():
    """Redirect root to text mode."""
    return render_template("text_mode.html", active_mode="text")


@bp.route("/text")
def text_mode():
    """Render the Text Mode page."""
    return render_template("text_mode.html", active_mode="text")
