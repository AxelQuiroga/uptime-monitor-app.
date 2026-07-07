import pytest
from sqlalchemy.exc import IntegrityError
from uptime.models import Target, Check


class TestTargetModel:
    """Tests for the Target model."""

    def test_create_target(self, session):
        """Create a Target and verify default values."""
        t = Target(name="My Target", url="https://example.com")
        session.add(t)
        session.commit()

        assert t.id is not None
        assert t.name == "My Target"
        assert t.url == "https://example.com"
        assert t.webhook_url is None
        assert t.interval_seconds == 30
        assert t.is_active is True
        assert t.created_at is not None

    def test_target_to_dict(self, session):
        """Verify to_dict() returns expected structure."""
        t = Target(
            name="Test Target",
            url="https://example.com",
            webhook_url="https://hooks.example.com",
        )
        session.add(t)
        session.commit()

        d = t.to_dict()
        assert d["id"] == t.id
        assert d["name"] == "Test Target"
        assert d["url"] == "https://example.com"
        assert d["webhook_url"] == "https://hooks.example.com"
        assert d["interval_seconds"] == 30
        assert d["is_active"] is True
        assert d["created_at"] == t.created_at.isoformat()

    def test_target_unique_url(self, session):
        """Creating two targets with the same URL raises IntegrityError."""
        t1 = Target(name="First", url="https://example.com")
        session.add(t1)
        session.commit()

        t2 = Target(name="Second", url="https://example.com")
        session.add(t2)
        with pytest.raises(IntegrityError):
            session.commit()


class TestCheckModel:
    """Tests for the Check model."""

    def test_create_check(self, session, target):
        """Create a Check linked to a Target."""
        c = Check(
            target_id=target.id,
            status_code=200,
            latency_ms=150.5,
            is_up=True,
        )
        session.add(c)
        session.commit()

        assert c.id is not None
        assert c.target_id == target.id
        assert c.status_code == 200
        assert c.latency_ms == 150.5
        assert c.is_up is True
        assert c.error_message is None

    def test_check_to_dict(self, session, target):
        """Verify Check.to_dict() returns expected structure."""
        c = Check(
            target_id=target.id,
            status_code=200,
            latency_ms=150.5,
            is_up=True,
        )
        session.add(c)
        session.commit()

        d = c.to_dict()
        assert d["id"] == c.id
        assert d["status_code"] == 200
        assert d["latency_ms"] == 150.5
        assert d["is_up"] is True
        assert d["error"] is None
        assert d["checked_at"] == c.created_at.isoformat()

    def test_target_checks_relationship(self, session, target):
        """Target.checks returns Checks ordered by created_at desc."""
        import time

        c1 = Check(target_id=target.id, status_code=200, latency_ms=100, is_up=True)
        session.add(c1)
        session.commit()
        time.sleep(0.01)

        c2 = Check(target_id=target.id, status_code=404, latency_ms=50, is_up=False)
        session.add(c2)
        session.commit()

        assert target.checks.count() == 2
        checks = target.checks.all()

        # Most recent first (ordered by created_at desc)
        assert checks[0].id == c2.id
        assert checks[1].id == c1.id
        assert checks[0].created_at > checks[1].created_at
