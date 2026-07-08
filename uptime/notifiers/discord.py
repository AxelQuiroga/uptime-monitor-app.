"""
Discord webhook notifier — sends messages via Discord Webhooks.
Expects value = full webhook URL like https://discord.com/api/webhooks/...
"""
import requests
from ..models import Target, Check


def send_discord(webhook_url: str, target: Target, check: Check, previous_up: bool | None) -> None:
    status, color, title, event_type = _build_meta(target, check, previous_up)

    discord_color = 0x22C55E if color == "green" else 0xEF4444

    payload = {
        "username": "Uptime Monitor",
        "embeds": [{
            "title": title,
            "color": discord_color,
            "fields": [
                {"name": "URL", "value": target.url, "inline": True},
                {"name": "Status", "value": status, "inline": True},
                {"name": "Event", "value": event_type, "inline": True},
                {"name": "Status Code", "value": str(check.status_code) if check.status_code else "N/A", "inline": True},
                {"name": "Latency", "value": f"{check.latency_ms:.0f}ms" if check.latency_ms else "N/A", "inline": True},
                {"name": "Error", "value": check.error_message or "None", "inline": False},
            ],
            "timestamp": check.created_at.isoformat() if check.created_at else None,
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
