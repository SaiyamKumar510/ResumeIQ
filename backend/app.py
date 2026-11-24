"""ResumeIQ Flask application.

Run from the project root (the folder that contains ``backend/``):

    python -m backend.app
    # or
    flask --app backend.app run
"""

import logging
import os

from flask import Flask, jsonify, request
from sqlalchemy.exc import InterfaceError, OperationalError, SQLAlchemyError
from werkzeug.exceptions import HTTPException

from .config import Config
from .database.db import db, init_db
from .routes import ApiError, analysis_bp, error_payload

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def create_app(config_object=Config) -> Flask:
    """Application factory: load config, set up the database, register routes and error handlers."""
    app = Flask(__name__)
    app.config.from_object(config_object)
    app.json.sort_keys = False  # keep the key order of the responses as written

    if not app.config["TESTING"] and not app.config["SQLALCHEMY_DATABASE_URI"].username:
        app.logger.warning("DB_USER is not set. Copy .env.example to .env and fill in the database settings.")

    init_db(app)
    app.register_blueprint(analysis_bp)
    register_error_handlers(app)
    register_cors(app)
    return app


def register_cors(app: Flask) -> None:
    """Optional CORS for a frontend served from another origin.

    Disabled unless ``CORS_ORIGINS`` is set (comma-separated origins, e.g.
    ``http://localhost:5173``). In development the Vite proxy makes this
    unnecessary. Only /api routes get the headers.
    """
    allowed = {o.strip().rstrip("/") for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()}
    if not allowed:
        return

    @app.after_request
    def add_cors_headers(response):
        origin = request.headers.get("Origin", "").rstrip("/")
        if request.path.startswith("/api") and origin in allowed:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Vary"] = "Origin"
        return response


def register_error_handlers(app: Flask) -> None:
    """Return every error as JSON: {"error": {"code", "message", "details"?}}."""

    @app.errorhandler(ApiError)
    def handle_api_error(error):
        return jsonify(error_payload(error.code, error.message, error.details)), error.status_code

    @app.errorhandler(SQLAlchemyError)
    def handle_database_error(error):
        db.session.rollback()
        app.logger.error("Database error: %s", error.__class__.__name__, exc_info=True)
        if isinstance(error, (OperationalError, InterfaceError)):
            return jsonify(error_payload("database_unavailable", "The database is not available. Please try again later.")), 503
        return jsonify(error_payload("database_error", "A database error occurred.")), 500

    @app.errorhandler(HTTPException)
    def handle_http_error(error):
        if error.code == 413:
            limit_mb = app.config["MAX_UPLOAD_BYTES"] / (1024 * 1024)
            return jsonify(error_payload("file_too_large", f"The upload is too large. The limit is {limit_mb:g} MB.")), 413
        code = (error.name or "error").lower().replace(" ", "_")
        return jsonify(error_payload(code, error.description)), error.code

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled error")
        return jsonify(error_payload("internal_error", "An unexpected error occurred.")), 500


if __name__ == "__main__":
    application = create_app()
    application.run(host=application.config["HOST"], port=application.config["PORT"], debug=application.config["DEBUG"])
