import pytest
from unittest.mock import patch, MagicMock
from uptime.models import Target, Check, AlertChannel


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


class TestReportRoutes:
    """Tests for /api/report/<id> and /api/report/<id>/timeline endpoints."""

    def test_report_endpoint(self, client, target, session):
        """GET /api/report/<id> returns 200 with report structure."""
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda idx: [10, 9, 90.0, 150.0, 500.0, 50.0][idx]

        with patch('uptime.routes.db.session.execute') as mock_exec:
            mock_exec.return_value.fetchone.return_value = mock_row
            resp = client.get(f"/api/report/{target.id}")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["uptime_pct"] == 90.0
            assert data["total_checks"] == 10
            assert data["target_id"] == target.id
            assert data["target_name"] == "Test"

    def test_report_timeline_endpoint(self, client, target, session):
        """GET /api/report/<id>/timeline returns timeline array."""
        from datetime import datetime, timezone
        mock_bucket = datetime.now(timezone.utc)
        mock_row = MagicMock()
        mock_row.__getitem__.side_effect = lambda idx: [
            mock_bucket, 10, 9, 90.0, 150.0, 500.0, 50.0
        ][idx]

        with patch('uptime.routes.db.session.execute') as mock_exec:
            mock_exec.return_value.fetchall.return_value = [mock_row]
            resp = client.get(f"/api/report/{target.id}/timeline?days=7")
            assert resp.status_code == 200
            data = resp.get_json()
            assert "timeline" in data
            assert len(data["timeline"]) == 1
            assert data["timeline"][0]["uptime_pct"] == 90.0
            assert data["timeline"][0]["total_checks"] == 10
            assert data["target_id"] == target.id

    def test_report_not_found(self, client):
        """GET /api/report/9999 returns 404."""
        resp = client.get("/api/report/9999")
        assert resp.status_code == 404


class TestAlertChannelRoutes:
    """Tests for /api/alert-channels CRUD endpoints."""

    def test_list_empty(self, client):
        """GET /api/alert-channels returns empty list."""
        resp = client.get("/api/alert-channels")
        assert resp.status_code == 200
        assert resp.json == []

    def test_create_slack(self, client, session):
        """POST with valid slack channel creates and returns 201."""
        resp = client.post(
            "/api/alert-channels",
            json={"type": "slack", "value": "https://hooks.slack.com/abc", "name": "Team"},
        )
        assert resp.status_code == 201
        data = resp.json
        assert data["type"] == "slack"
        assert data["value"] == "https://hooks.slack.com/abc"
        assert data["name"] == "Team"
        assert data["is_active"] is True
        assert data["target_id"] is None

    def test_create_discord(self, client):
        """POST with valid discord channel."""
        resp = client.post(
            "/api/alert-channels", json={"type": "discord", "value": "https://discord.com/api/webhooks/x"}
        )
        assert resp.status_code == 201
        assert resp.json["type"] == "discord"

    def test_create_email(self, client):
        """POST with valid email channel."""
        resp = client.post(
            "/api/alert-channels", json={"type": "email", "value": "ops@example.com"}
        )
        assert resp.status_code == 201
        assert resp.json["type"] == "email"

    def test_create_scoped_to_target(self, client, target):
        """POST with target_id scopes the channel."""
        resp = client.post(
            "/api/alert-channels",
            json={"type": "slack", "value": "https://hooks.slack.com/t", "target_id": target.id},
        )
        assert resp.status_code == 201
        assert resp.json["target_id"] == target.id

    def test_create_scoped_to_nonexistent_target(self, client):
        """POST with invalid target_id returns 404."""
        resp = client.post(
            "/api/alert-channels",
            json={"type": "slack", "value": "https://hooks.slack.com/t", "target_id": 999},
        )
        assert resp.status_code == 404

    def test_create_invalid_type(self, client):
        """POST with invalid type returns 400."""
        resp = client.post(
            "/api/alert-channels", json={"type": "pagerduty", "value": "https://hooks.example.com"}
        )
        assert resp.status_code == 400
        assert "type must be" in resp.json["error"]

    def test_create_missing_value(self, client):
        """POST without value returns 400."""
        resp = client.post("/api/alert-channels", json={"type": "slack"})
        assert resp.status_code == 400
        assert "value" in resp.json["error"]

    def test_create_empty_body(self, client):
        """POST with no body returns 400."""
        resp = client.post("/api/alert-channels", data="", content_type="application/json")
        assert resp.status_code == 400

    def test_list_after_create(self, client):
        """GET returns created channels."""
        client.post("/api/alert-channels", json={"type": "slack", "value": "https://hooks.slack.com/a"})
        client.post("/api/alert-channels", json={"type": "discord", "value": "https://discord.com/w"})

        resp = client.get("/api/alert-channels")
        assert resp.status_code == 200
        assert len(resp.json) == 2

    def test_update_channel(self, client, session):
        """PUT updates channel fields."""
        ch = AlertChannel(type="slack", value="https://hooks.slack.com/old")
        session.add(ch)
        session.commit()

        resp = client.put(
            f"/api/alert-channels/{ch.id}",
            json={"value": "https://hooks.slack.com/new", "name": "Updated", "is_active": False},
        )
        assert resp.status_code == 200
        assert resp.json["value"] == "https://hooks.slack.com/new"
        assert resp.json["name"] == "Updated"
        assert resp.json["is_active"] is False

    def test_update_not_found(self, client):
        """PUT on non-existent id returns 404."""
        resp = client.put("/api/alert-channels/999", json={"value": "https://hooks.example.com"})
        assert resp.status_code == 404

    def test_toggle_channel(self, client, session):
        """PATCH toggle flips is_active."""
        ch = AlertChannel(type="slack", value="https://hooks.slack.com/t")
        session.add(ch)
        session.commit()

        assert ch.is_active is True

        resp = client.patch(f"/api/alert-channels/{ch.id}/toggle")
        assert resp.status_code == 200
        assert resp.json["is_active"] is False

        resp = client.patch(f"/api/alert-channels/{ch.id}/toggle")
        assert resp.status_code == 200
        assert resp.json["is_active"] is True

    def test_delete_channel(self, client, session):
        """DELETE removes the channel."""
        ch = AlertChannel(type="slack", value="https://hooks.slack.com/del")
        session.add(ch)
        session.commit()

        resp = client.delete(f"/api/alert-channels/{ch.id}")
        assert resp.status_code == 200
        assert resp.json["message"] == "deleted"

        # Verify gone
        resp = client.get("/api/alert-channels")
        assert len(resp.json) == 0

    def test_delete_not_found(self, client):
        """DELETE on non-existent id returns 404."""
        resp = client.delete("/api/alert-channels/999")
        assert resp.status_code == 404
