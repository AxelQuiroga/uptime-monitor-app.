import pytest
import responses
from uptime.models import Check
from uptime.notifier import send_alert


def _make_check(session, target, status_code, is_up):
    """Helper to create and persist a Check with minimal fields."""
    c = Check(
        target_id=target.id,
        status_code=status_code,
        is_up=is_up,
        latency_ms=100.0,
    )
    session.add(c)
    session.commit()
    return c


class TestSendAlert:
    """Tests for notifier.send_alert."""

    @responses.activate
    def test_send_alert_down(self, app, session, target_with_webhook):
        """UP → DOWN transition sends a webhook alert."""
        responses.add(
            responses.POST, "https://hooks.example.com/alert", status=200
        )
        check = _make_check(session, target_with_webhook, 500, is_up=False)

        send_alert(target_with_webhook, check, previous_up=True)

        assert len(responses.calls) == 1
        call = responses.calls[0]
        assert call.request.url == "https://hooks.example.com/alert"
        assert call.request.method == "POST"

    @responses.activate
    def test_send_alert_recovered(self, app, session, target_with_webhook):
        """DOWN → UP transition sends a 'recovered' webhook."""
        responses.add(
            responses.POST, "https://hooks.example.com/alert", status=200
        )
        check = _make_check(session, target_with_webhook, 200, is_up=True)

        send_alert(target_with_webhook, check, previous_up=False)

        assert len(responses.calls) == 1
        call = responses.calls[0]
        assert call.request.url == "https://hooks.example.com/alert"

    @responses.activate
    def test_send_alert_no_webhook(self, app, session, target):
        """No webhook_url configured → no HTTP request is made."""
        check = _make_check(session, target, 500, is_up=False)

        send_alert(target, check, previous_up=True)

        assert len(responses.calls) == 0

    @responses.activate
    def test_send_alert_consecutive_down(self, app, session, target_with_webhook):
        """DOWN → DOWN does NOT send an alert (spam prevention)."""
        check = _make_check(session, target_with_webhook, 500, is_up=False)

        send_alert(target_with_webhook, check, previous_up=False)

        assert len(responses.calls) == 0

    @responses.activate
    def test_send_alert_first_check_down(self, app, session, target_with_webhook):
        """First check is DOWN → sends alert (FIRST_CHECK_DOWN)."""
        responses.add(
            responses.POST, "https://hooks.example.com/alert", status=200
        )
        check = _make_check(session, target_with_webhook, 500, is_up=False)

        send_alert(target_with_webhook, check, previous_up=None)

        assert len(responses.calls) == 1
        call = responses.calls[0]
        assert call.request.url == "https://hooks.example.com/alert"

    @responses.activate
    def test_send_alert_first_check_up(self, app, session, target_with_webhook):
        """First check is UP → no alert (nothing to notify)."""
        check = _make_check(session, target_with_webhook, 200, is_up=True)

        send_alert(target_with_webhook, check, previous_up=None)

        assert len(responses.calls) == 0

    @responses.activate
    def test_send_alert_webhook_failure(self, app, session, target_with_webhook):
        """Webhook returns 500 → no crash, error is logged gracefully."""
        responses.add(
            responses.POST, "https://hooks.example.com/alert", status=500
        )
        check = _make_check(session, target_with_webhook, 500, is_up=False)

        # Should not raise any exception
        send_alert(target_with_webhook, check, previous_up=True)

        assert len(responses.calls) == 1


class TestDispatch:
    """Tests for the AlertChannel dispatcher path."""

    @responses.activate
    def test_dispatch_slack(self, app, session, target):
        """AlertChannel type=slack sends via webhook."""
        responses.add(responses.POST, "https://hooks.slack.com/abc", status=200)

        from uptime.models import AlertChannel
        ch = AlertChannel(type="slack", value="https://hooks.slack.com/abc", name="Test")
        session.add(ch)
        session.commit()

        check = _make_check(session, target, 500, is_up=False)
        send_alert(target, check, previous_up=True)

        assert len(responses.calls) == 1
        call = responses.calls[0]
        assert call.request.url == "https://hooks.slack.com/abc"
        assert call.request.method == "POST"

    @responses.activate
    def test_dispatch_discord(self, app, session, target):
        """AlertChannel type=discord sends via webhook."""
        responses.add(responses.POST, "https://discord.com/api/webhooks/xyz", status=200)

        from uptime.models import AlertChannel
        ch = AlertChannel(type="discord", value="https://discord.com/api/webhooks/xyz")
        session.add(ch)
        session.commit()

        check = _make_check(session, target, 500, is_up=False)
        send_alert(target, check, previous_up=True)

        assert len(responses.calls) == 1

    @responses.activate
    def test_dispatch_global_and_scoped(self, app, session, target):
        """Both global + per-target channels receive the alert."""
        responses.add(responses.POST, "https://hooks.global.com/", status=200)
        responses.add(responses.POST, "https://hooks.scoped.com/", status=200)

        from uptime.models import AlertChannel
        global_ch = AlertChannel(type="slack", value="https://hooks.global.com/", name="Global")
        scoped_ch = AlertChannel(type="slack", value="https://hooks.scoped.com/", target_id=target.id, name="Scoped")
        session.add_all([global_ch, scoped_ch])
        session.commit()

        check = _make_check(session, target, 500, is_up=False)
        send_alert(target, check, previous_up=True)

        assert len(responses.calls) == 2

    @responses.activate
    def test_dispatch_inactive_channels_ignored(self, app, session, target):
        """Inactive channels are NOT notified."""
        responses.add(responses.POST, "https://hooks.active.com/", status=200)

        from uptime.models import AlertChannel
        active = AlertChannel(type="slack", value="https://hooks.active.com/", is_active=True)
        inactive = AlertChannel(type="slack", value="https://hooks.inactive.com/", is_active=False)
        session.add_all([active, inactive])
        session.commit()

        check = _make_check(session, target, 500, is_up=False)
        send_alert(target, check, previous_up=True)

        assert len(responses.calls) == 1
        assert responses.calls[0].request.url == "https://hooks.active.com/"

    @responses.activate
    def test_dispatch_legacy_plus_channels(self, app, session, target_with_webhook):
        """Both legacy webhook + AlertChannel dispatch fire."""
        # Legacy webhook response + AlertChannel response
        responses.add(responses.POST, "https://hooks.example.com/alert", status=200)
        responses.add(responses.POST, "https://hooks.newchannel.com/", status=200)

        from uptime.models import AlertChannel
        ch = AlertChannel(type="slack", value="https://hooks.newchannel.com/")
        session.add(ch)
        session.commit()

        check = _make_check(session, target_with_webhook, 500, is_up=False)
        send_alert(target_with_webhook, check, previous_up=True)

        assert len(responses.calls) == 2
