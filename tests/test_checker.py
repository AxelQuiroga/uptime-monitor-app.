import pytest
import responses
import requests
from unittest.mock import patch
from uptime.checker import check_url
from uptime.models import Check


class TestCheckURL:
    """Tests for check_url HTTP behavior."""

    @responses.activate
    def test_check_url_success(self, app, session, target):
        """200 OK → is_up=True, latency recorded, status_code=200."""
        responses.add(responses.GET, "https://example.com", status=200, body="OK")
        check = check_url(target)

        assert check.is_up is True
        assert check.status_code == 200
        assert check.latency_ms is not None
        assert check.latency_ms > 0
        assert check.error_message is None

    @responses.activate
    def test_check_url_404(self, app, session, target):
        """404 → is_up=False."""
        responses.add(responses.GET, "https://example.com", status=404)
        check = check_url(target)

        assert check.is_up is False
        assert check.status_code == 404

    @responses.activate
    def test_check_url_500(self, app, session, target):
        """500 → is_up=False."""
        responses.add(responses.GET, "https://example.com", status=500)
        check = check_url(target)

        assert check.is_up is False
        assert check.status_code == 500

    @responses.activate
    def test_check_url_timeout(self, app, session, target):
        """Timeout → is_up=False, error_message='Timeout after 10s'."""
        responses.add(responses.GET, "https://example.com", body=requests.Timeout())
        check = check_url(target)

        assert check.is_up is False
        assert check.status_code is None
        assert check.latency_ms is None
        assert check.error_message == "Timeout after 10s"

    @responses.activate
    def test_check_url_connection_error(self, app, session, target):
        """Connection failure → is_up=False, error_message='Connection failed'."""
        responses.add(
            responses.GET, "https://example.com", body=requests.ConnectionError()
        )
        check = check_url(target)

        assert check.is_up is False
        assert check.status_code is None
        assert check.latency_ms is None
        assert check.error_message == "Connection failed"

    @responses.activate
    def test_check_url_creates_check_record(self, app, session, target):
        """Verify the Check is saved to the database."""
        responses.add(responses.GET, "https://example.com", status=200, body="OK")

        assert Check.query.count() == 0
        check = check_url(target)

        assert Check.query.count() == 1
        saved = Check.query.first()
        assert saved.id == check.id
        assert saved.target_id == target.id
        assert saved.is_up is True

    @responses.activate
    def test_check_url_3xx_redirect(self, app, session, target):
        """301 with allow_redirects=True → follows redirect, is_up=True."""
        responses.add(
            responses.GET,
            "https://example.com",
            status=301,
            headers={"Location": "https://example.com/final"},
        )
        responses.add(
            responses.GET, "https://example.com/final", status=200, body="OK"
        )
        check = check_url(target)

        assert check.is_up is True
        assert check.status_code == 200  # Final status after redirect


class TestCheckNotifications:
    """Tests for check_url notification logic (with send_alert mocked)."""

    @responses.activate
    @patch("uptime.checker.send_alert")
    def test_check_detects_down_transition(
        self, mock_send_alert, app, session, target
    ):
        """UP → DOWN transition triggers alert."""
        prev = Check(
            target_id=target.id, status_code=200, latency_ms=100, is_up=True
        )
        session.add(prev)
        session.commit()

        responses.add(responses.GET, "https://example.com", status=500)
        check = check_url(target)

        assert check.is_up is False
        mock_send_alert.assert_called_once()
        args, _ = mock_send_alert.call_args
        assert args[0] == target
        assert args[1] == check
        assert args[2] is True  # previous_up was True

    @responses.activate
    @patch("uptime.checker.send_alert")
    def test_check_detects_up_transition(
        self, mock_send_alert, app, session, target
    ):
        """DOWN → UP transition triggers alert."""
        prev = Check(
            target_id=target.id, status_code=500, latency_ms=100, is_up=False
        )
        session.add(prev)
        session.commit()

        responses.add(responses.GET, "https://example.com", status=200, body="OK")
        check = check_url(target)

        assert check.is_up is True
        mock_send_alert.assert_called_once()
        args, _ = mock_send_alert.call_args
        assert args[2] is False  # previous_up was False

    @responses.activate
    @patch("uptime.checker.send_alert")
    def test_check_same_status_no_alert(
        self, mock_send_alert, app, session, target
    ):
        """DOWN → DOWN does NOT trigger alert (no spam)."""
        prev = Check(
            target_id=target.id, status_code=500, latency_ms=100, is_up=False
        )
        session.add(prev)
        session.commit()

        responses.add(responses.GET, "https://example.com", status=503)
        check = check_url(target)

        assert check.is_up is False
        mock_send_alert.assert_not_called()
