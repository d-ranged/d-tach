from pathlib import Path

from flask import Flask, redirect, request, url_for

__version__ = "1.2.0"


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
    from app.services.language_registry import LanguageRegistry
    from app.services.user_settings import UserSettings

    app.user_settings = UserSettings(  # type: ignore[attr-defined]
        settings_path=Path(app.root_path).parent / "user_settings.json"
    )

    # Eager mode loads every enabled+installed language at startup; lazy mode
    # starts with nothing loaded and loads on demand via LanguageDetector.
    registry = LanguageRegistry()
    if app.user_settings.loading_strategy == "lazy":
        startup_languages: list[str] = []
    else:
        installed = set(registry.installed_languages())
        startup_languages = [c for c in app.user_settings.enabled_languages if c in installed]

    app.anonymizer = Anonymizer(languages=startup_languages)  # type: ignore[attr-defined]
    registry.set_anonymizer(app.anonymizer)
    app.language_registry = registry  # type: ignore[attr-defined]
    app.language_detector = LanguageDetector(registry=registry)  # type: ignore[attr-defined]

    from app.services.file_processor import FileProcessor
    from app.services.folder_processor import FolderProcessor

    app.file_processor = FileProcessor(  # type: ignore[attr-defined]
        anonymizer=app.anonymizer,
        language_detector=app.language_detector,
    )
    app.folder_processor = FolderProcessor(  # type: ignore[attr-defined]
        file_processor=app.file_processor,
    )

    from app.services.class_list_importer import ClassListImporter
    from app.services.document_processor import DocumentProcessor

    app.class_list_importer = ClassListImporter(  # type: ignore[attr-defined]
        document_processor=DocumentProcessor(),
    )

    from app.routes.text_routes import bp as text_bp
    from app.routes.document_routes import bp as document_bp
    from app.routes.browse_routes import bp as browse_bp
    from app.routes.settings_routes import bp as settings_bp
    from app.routes.restore_routes import bp as restore_bp
    from app.routes.setup_routes import bp as setup_bp

    app.register_blueprint(text_bp)
    app.register_blueprint(document_bp)
    app.register_blueprint(browse_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(restore_bp)
    app.register_blueprint(setup_bp)

    _EXEMPT_ENDPOINTS = {"setup.setup_page", "setup.start_setup_install", "setup.setup_status", "setup.complete_setup", "static"}

    @app.before_request
    def require_language_setup():
        """Redirect to the first-launch language setup screen until it is completed."""
        if app.user_settings.language_setup_complete:
            return None
        if request.endpoint in _EXEMPT_ENDPOINTS:
            return None
        return redirect(url_for("setup.setup_page"))

    return app
