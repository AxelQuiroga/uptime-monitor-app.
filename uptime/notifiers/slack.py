"""
Slack webhook notifier — sends messages via Incoming Webhooks.
Expects value = full webhook URL like https://hooks.slack.com/services/...
"""
import requests
from ..models import Target, Check


def send_slack(webhook_url: str, target: Target, check: Check, previous_up: bool | None) -> None:
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

    resp = requests.post(webhook_url, json=payload, timeout=10)
    resp.raise_for_status()


def _build_meta(target, check, previous_up):
    if previous_up is None:
        return "DOWN", "red", f"[DOWN] {target.name} (nuevo target)", "FIRST_CHECK_DOWN"
    if previous_up and not check.is_up:
        return "DOWN", "red", f"[DOWN] {target.name}", "DOWN"
    if not previous_up and check.is_up:
        return "UP", "green", f"[UP] {target.name} — recovered", "UP"
    return "UP", "green", f"[UP] {target.name}", "UP"
