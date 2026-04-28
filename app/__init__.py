from pathlib import Path

from flask import Flask

__version__ = "1.1.0"


def create_app() -> Flask:
    """Create and configure the Flask application instance."""
    app = Flask(__name__)

    @app.context_processor
    def inject_version() -> dict:
        """Make app_version available in all templates."""
        return {"app_version": __version__}

    # Initialise long-lived services once so spaCy models load only at startup.
    # These are attached to the app object and accessed via current_app in routes.
    from app.services.anonymizer import Anonymizer
    from app.services.language_detector import LanguageDetector
    from app.services.user_settings import UserSettings

    app.anonymizer = Anonymizer()  # type: ignore[attr-defined]
    app.language_detector = LanguageDetector()  # type: ignore[attr-defined]
    app.user_settings = UserSettings(  # type: ignore[attr-defined]
        settings_path=Path(app.root_path).parent / "user_settings.json"
    )

    from app.services.file_processor import FileProcessor
    from app.services.folder_processor import FolderProcessor

    app.file_processor = FileProcessor(  # type: ignore[attr-defined]
        anonymizer=app.anonymizer,
        language_detector=app.language_detector,
    )
    app.folder_processor = FolderProcessor(  # type: ignore[attr-defined]
        file_processor=app.file_processor,
    )

    from app.routes.text_routes import bp as text_bp
    from app.routes.document_routes import bp as document_bp
    from app.routes.browse_routes import bp as browse_bp

    app.register_blueprint(text_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(browse_bp)

    return app
