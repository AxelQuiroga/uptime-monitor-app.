import pytest
from uptime.models import Target, Check


class TestTargetRoutes:
    """Tests for /api/targets endpoints."""

    def test_list_targets_empty(self, client):
        """GET /api/targets returns empty list when no targets exist."""
        resp = client.get("/api/targets")
        assert resp.status_code == 200
        assert resp.json == []

    def test_create_target(self, client):
        """POST /api/targets with valid data returns 201."""
        resp = client.post(
            "/api/targets",
            json={"name": "My Target", "url": "https://example.com"},
        )
        assert resp.status_code == 201
        data = resp.json
        assert data["name"] == "My Target"
        assert data["url"] == "https://example.com"
        assert data["id"] is not None
        assert data["webhook_url"] is None
        assert data["is_active"] is True
        assert data["interval_seconds"] == 30

    def test_create_target_with_webhook(self, client):
        """POST /api/targets with webhook_url stores it correctly."""
        resp = client.post(
            "/api/targets",
            json={
                "name": "With Webhook",
                "url": "https://example.com",
                "webhook_url": "https://hooks.example.com/alert",
            },
        )
        assert resp.status_code == 201
        assert resp.json["webhook_url"] == "https://hooks.example.com/alert"

    def test_create_target_missing_url(self, client):
        """POST /api/targets without url returns 400."""
        resp = client.post("/api/targets", json={"name": "No URL"})
        assert resp.status_code == 400
        assert resp.json["error"] == "url is required"

    def test_create_target_empty_body(self, client):
        """POST /api/targets with no body returns 400."""
        resp = client.post(
            "/api/targets", data="", content_type="application/json"
        )
        assert resp.status_code == 400

    def test_create_target_duplicate(self, client):
        """POST /api/targets with existing url returns 409."""
        client.post("/api/targets", json={"url": "https://example.com"})

        resp = client.post(
            "/api/targets", json={"url": "https://example.com"}
        )
        assert resp.status_code == 409
        assert resp.json["error"] == "target already exists"

    def test_delete_target(self, client, session):
        """DELETE /api/targets/<id> removes the target."""
        t = Target(name="Test", url="https://example.com")
        session.add(t)
        session.commit()

        resp = client.delete(f"/api/targets/{t.id}")
        assert resp.status_code == 200
        assert resp.json["message"] == "deleted"
        assert Target.query.get(t.id) is None

    def test_delete_target_not_found(self, client):
        """DELETE /api/targets/<id> for non-existent id returns 404."""
        resp = client.delete("/api/targets/999")
        assert resp.status_code == 404


class TestStatusRoutes:
    """Tests for /api/status endpoint."""

    def test_get_status(self, client, session):
        """GET /api/status returns status info for active targets."""
        t = Target(name="Test", url="https://example.com", is_active=True)
        session.add(t)
        session.commit()

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 1
        assert data[0]["id"] == t.id
        assert data[0]["name"] == "Test"
        assert data[0]["url"] == "https://example.com"
        assert data[0]["status"] == "down"  # No checks yet
        assert data[0]["last_check"] is None

    def test_get_status_with_check(self, client, session):
        """GET /api/status reflects last check status."""
        t = Target(name="Test", url="https://example.com", is_active=True)
        session.add(t)
        session.commit()

        c = Check(
            target_id=t.id, status_code=200, latency_ms=100, is_up=True
        )
        session.add(c)
        session.commit()

        resp = client.get("/api/status")
        assert resp.status_code == 200
        data = resp.json
        assert data[0]["status"] == "up"
        assert data[0]["last_check"] is not None
        assert data[0]["last_check"]["status_code"] == 200

    def test_get_status_empty(self, client):
        """GET /api/status returns empty list with no active targets."""
        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert resp.json == []

    def test_get_status_inactive_target(self, client, session):
        """Inactive targets are excluded from status."""
        active = Target(name="Active", url="https://active.com", is_active=True)
        inactive = Target(
            name="Inactive", url="https://inactive.com", is_active=False
        )
        session.add(active)
        session.add(inactive)
        session.commit()

        resp = client.get("/api/status")
        assert resp.status_code == 200
        assert len(resp.json) == 1
        assert resp.json[0]["name"] == "Active"


class TestHistoryRoutes:
    """Tests for /api/history/<id> endpoint."""

    def test_get_history(self, client, session):
        """GET /api/history/<id> returns checks for the target."""
        t = Target(name="Test", url="https://example.com")
        session.add(t)
        session.commit()

        c = Check(
            target_id=t.id, status_code=200, latency_ms=100, is_up=True
        )
        session.add(c)
        session.commit()

        resp = client.get(f"/api/history/{t.id}")
        assert resp.status_code == 200
        data = resp.json
        assert len(data) == 1
        assert data[0]["status_code"] == 200
        assert data[0]["is_up"] is True

    def test_get_history_empty(self, client, session):
        """GET /api/history/<id> returns empty list when no checks exist."""
        t = Target(name="Test", url="https://example.com")
        session.add(t)
        session.commit()

        resp = client.get(f"/api/history/{t.id}")
        assert resp.status_code == 200
        assert resp.json == []

    def test_get_history_limit(self, client, session):
        """GET /api/history/<id>?limit=N limits the results."""
        t = Target(name="Test", url="https://example.com")
        session.add(t)
        session.commit()

        for _ in range(5):
            c = Check(
                target_id=t.id, status_code=200, latency_ms=100, is_up=True
            )
            session.add(c)
        session.commit()

        resp = client.get(f"/api/history/{t.id}?limit=3")
        assert resp.status_code == 200
        assert len(resp.json) == 3

    def test_get_history_default_limit(self, client, session):
        """Default limit is 20 checks per request."""
        t = Target(name="Test", url="https://example.com")
        session.add(t)
        session.commit()

        for _ in range(25):
            c = Check(
                target_id=t.id, status_code=200, latency_ms=100, is_up=True
            )
            session.add(c)
        session.commit()

        resp = client.get(f"/api/history/{t.id}")
        assert resp.status_code == 200
        assert len(resp.json) == 20
