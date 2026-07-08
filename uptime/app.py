import os
import secrets
from flask import Flask
from flask_login import LoginManager
from .database import db, get_db_uri
from .routes import api
from .dashboard_routes import dashboard
from .status_routes import status_page
from .auth_routes import auth
from .models import AdminUser

login_manager = LoginManager()
login_manager.login_view = "auth.login_page"
login_manager.login_message = None  # No flash message on redirect


@login_manager.user_loader
def load_user(user_id):
    """Flask-Login callback — always returns the singleton admin."""
    if user_id == "admin":
        return AdminUser()
    return None


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = get_db_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # --- Auth ---
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        if os.getenv("FLASK_DEBUG", "0") == "1":
            secret_key = secrets.token_hex(32)
        else:
            raise RuntimeError(
                "SECRET_KEY environment variable is required in production. "
                "Generate one with: python3 -c \"import secrets; print(secrets.token_hex(32))\""
            )
    app.config["SECRET_KEY"] = secret_key
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(status_page)                         # / → public status
    app.register_blueprint(dashboard, url_prefix="/dashboard")  # /dashboard → requires login
    app.register_blueprint(auth)                                 # /login, /logout
    app.register_blueprint(api)                                  # /api → API endpoints
    return app
