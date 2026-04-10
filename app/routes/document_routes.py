from flask import Blueprint, render_template

bp = Blueprint("document", __name__)


@bp.route("/document")
def document_mode():
    """Render the Document Mode page."""
    return render_template("document_mode.html", active_mode="document")
