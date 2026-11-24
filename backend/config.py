"""Application configuration.

All secrets and connection settings come from environment variables (see
``.env.example`` in the project root). A ``.env`` file in the project root is
loaded automatically if it exists. Nothing sensitive is hard-coded here.
"""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy.engine import URL
from sqlalchemy.pool import StaticPool

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Room for multipart headers and the text fields around an uploaded PDF.
_REQUEST_OVERHEAD_BYTES = 1024 * 1024


def build_mysql_url() -> URL:
    """Build the MySQL connection URL from DB_* environment variables.

    ``URL.create`` escapes special characters in the password, so passwords
    containing ``@`` or ``/`` work. DB_USER and DB_PASSWORD have no defaults.
    """
    return URL.create(
        drivername="mysql+pymysql",
        username=os.getenv("DB_USER", ""),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        database=os.getenv("DB_NAME", "resumeiq"),
        query={"charset": "utf8mb4"},
    )


class Config:
    """Default configuration: MySQL through PyMySQL."""

    SQLALCHEMY_DATABASE_URI = build_mysql_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,   # drop dead connections instead of failing on them
        "pool_recycle": 280,     # stay below MySQL's idle-connection timeout
        "connect_args": {"connect_timeout": 5},  # fail fast when MySQL is down
    }

    MAX_UPLOAD_MB = float(os.getenv("MAX_UPLOAD_MB", "5"))
    MAX_UPLOAD_BYTES = int(MAX_UPLOAD_MB * 1024 * 1024)
    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES + _REQUEST_OVERHEAD_BYTES

    HOST = os.getenv("FLASK_HOST", "127.0.0.1")
    PORT = int(os.getenv("FLASK_PORT", "5000"))
    DEBUG = os.getenv("FLASK_DEBUG", "0").lower() in {"1", "true", "yes"}
    TESTING = False


class TestingConfig(Config):
    """Used by the automated tests: in-memory SQLite, never touches MySQL."""

    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "poolclass": StaticPool,  # one shared in-memory database per app
        "connect_args": {"check_same_thread": False},
    }
