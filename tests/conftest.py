import pytest
from uptime.app import create_app
from uptime.database import db
from uptime.models import Target


@pytest.fixture(scope="function")
def app(monkeypatch):
    """Create a Flask app with in-memory SQLite database."""
    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("ADMIN_PASSWORD", "testpass")
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-for-pytest-1234567890")
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()

    yield app

    with app.app_context():
        db.session.rollback()
        db.drop_all()
        db.engine.dispose()


@pytest.fixture
def client(app):
    """Test client for the Flask app (pre-authenticated)."""
    c = app.test_client()
    c.post("/login", data={"password": "testpass"})
    return c


@pytest.fixture
def session(app):
    """Database session within app context."""
    with app.app_context():
        yield db.session


@pytest.fixture
def target(session):
    """Create a basic active target."""
    t = Target(name="Test", url="https://example.com", is_active=True)
    session.add(t)
    session.commit()
    return t


@pytest.fixture
def target_with_webhook(session):
    """Create an active target with a webhook URL."""
    t = Target(
        name="Test Webhook",
        url="https://example.com",
        webhook_url="https://hooks.example.com/alert",
        is_active=True,
    )
    session.add(t)
    session.commit()
    return t
