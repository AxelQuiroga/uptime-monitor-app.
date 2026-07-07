from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def get_db_uri():
    """
    Returns the database URI from environment or a local-dev default.

    ⚠️ PRODUCTION: Always set DATABASE_URL via environment variables
       (or Docker secrets). The fallback below is for local development
       ONLY and MUST NOT be used in production.
    """
    return os.getenv(
        "DATABASE_URL",
        "postgresql://admin:secret123@localhost:5432/devopsdb"
    )
