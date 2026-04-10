from flask import Flask


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)

    from app.routes.text_routes import bp as text_bp
    from app.routes.document_routes import bp as document_bp

    app.register_blueprint(text_bp)
    app.register_blueprint(document_bp)

    return app
