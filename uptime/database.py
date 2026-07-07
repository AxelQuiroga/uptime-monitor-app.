from flask_sqlalchemy import SQLAlchemy
import os

db = SQLAlchemy()

def get_db_uri():
    return os.getenv(
        "DATABASE_URL",
        "postgresql://admin:secret123@localhost:5432/devopsdb"
    )
