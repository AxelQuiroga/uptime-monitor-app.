"""
Alert dispatcher — called by checker when a target changes state.

- Legacy path: sends to target.webhook_url (old per-target Slack webhook)
- New path: dispatches through AlertChannel records (global + per-target)
"""
import requests
import logging

from .notifiers import dispatch
from .models import Target, Check

log = logging.getLogger("notifier")


def send_alert(target: Target, check: Check, previous_up: bool | None) -> None:
    """Send alert on state transition. Called by checker."""
    # --- Spam filters ---
    if previous_up is False and not check.is_up:
        # Ya estaba DOWN, sigue DOWN — no spam
        return

    if previous_up is None and check.is_up:
        # Primera vez y está UP — no hay nada que notificar
        return

    if previous_up is True and check.is_up:
        # Sigue igual, no alertar
        return

    # --- Legacy path: per-target webhook_url ---
    if target.webhook_url:
        _send_legacy_slack(target, check, previous_up)

    # --- New path: AlertChannel dispatcher ---
    dispatch(target, check, previous_up)


# ── Legacy ────────────────────────────────────────────────────────────────

def _send_legacy_slack(target: Target, check: Check, previous_up: bool | None) -> None:
    status, color, title, event_type = _build_meta(target, check, previous_up)

    payload = {
        "text": title,
        "attachments": [{
            "color": color,
            "fields": [
                {"title": "URL", "value": target.url, "short": True},
                {"title": "Status", "value": status, "short": True},
                {"title": "Event", "value": event_type, "short": True},
                {"title": "Status Code", "value": str(check.status_code) if check.status_code else "N/A", "short": True},
                {"title": "Latency", "value": f"{check.latency_ms:.0f}ms" if check.latency_ms else "N/A", "short": True},
                {"title": "Error", "value": check.error_message or "None", "short": False},
            ],
            "ts": check.created_at.timestamp() if check.created_at else 0,
        }]
    }

    try:
        resp = requests.post(target.webhook_url, json=payload, timeout=10)
        log.info("Legacy alert sent to %s: %s", target.webhook_url, resp.status_code)
    except requests.ConnectionError:
        log.error("Failed to connect to webhook %s", target.webhook_url)
    except requests.Timeout:
        log.error("Timeout sending alert to %s", target.webhook_url)
    except Exception as e:
        log.error("Failed to send legacy alert: %s", e)


def _build_meta(target, check, previous_up):
    if previous_up is None:
        return "DOWN", "red", f"[DOWN] {target.name} (nuevo target)", "FIRST_CHECK_DOWN"
    if previous_up and not check.is_up:
        return "DOWN", "red", f"[DOWN] {target.name}", "DOWN"
    if not previous_up and check.is_up:
        return "UP", "green", f"[UP] {target.name} — recovered", "UP"
    return "UP", "green", f"[UP] {target.name}", "UP"
