from flask import Flask
from .database import db, get_db_uri
from .routes import api
from .dashboard_routes import dashboard
from .status_routes import status_page

def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = get_db_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    app.register_blueprint(status_page)                         # / → public status
    app.register_blueprint(dashboard, url_prefix="/dashboard")  # /dashboard → admin
    app.register_blueprint(api)                                  # /api → API endpoints
    return app
