"""Database setup: the shared SQLAlchemy instance and connection helpers."""

import logging

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

db = SQLAlchemy()

_SCHEMA_READY_KEY = "resumeiq_schema_ready"


def ensure_schema() -> bool:
    """Create the tables if they do not exist yet. Returns True when they are ready.

    Never raises: if the database is unreachable the problem is logged and
    ``False`` is returned, so the app can still start and report the problem
    through ``/api/health``. The next call retries, so the app recovers once
    MySQL becomes available.
    """
    if current_app.extensions.get(_SCHEMA_READY_KEY):
        return True
    try:
        from . import models  # noqa: F401  (registers the models on db.metadata)

        db.create_all()
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.warning("Could not create/verify the database schema: %s", exc.__class__.__name__)
        logger.debug("Schema error details", exc_info=True)
        return False
    current_app.extensions[_SCHEMA_READY_KEY] = True
    return True


def init_db(app) -> bool:
    """Attach SQLAlchemy to the app and try to create the schema once at startup."""
    db.init_app(app)
    with app.app_context():
        ready = ensure_schema()
    if not ready:
        app.logger.warning(
            "Database not reachable at startup. The app is running; /api/health "
            "reports the problem and the schema is created once the database is up."
        )
    return ready


def check_database():
    """Return ``(ok, message)`` describing the database connection.

    The message is deliberately generic: driver errors can contain host names
    or user names, so details go to the log only.
    """
    try:
        db.session.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.warning("Database health check failed: %s", exc.__class__.__name__)
        logger.debug("Health check details", exc_info=True)
        return False, "Could not connect to the database."
    if not ensure_schema():
        return False, "Connected, but the database tables could not be created."
    return True, "Database connection is working."
