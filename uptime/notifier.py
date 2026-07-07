import requests
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("notifier")

def send_alert(target, check, previous_up):
    """Manda alerta si el estado cambió de UP a DOWN (o viceversa)."""
    if target.webhook_url:
        if not previous_up and not check.is_up:
            # Ya estaba DOWN, no spammeamos — solo registramos
            return

        status = "UP" if check.is_up else "DOWN"
        color = "green" if check.is_up else "red"

        payload = {
            "text": f"[{status}] {target.name}",
            "attachments": [{
                "color": color,
                "fields": [
                    {"title": "URL", "value": target.url, "short": True},
                    {"title": "Status", "value": status, "short": True},
                    {"title": "Status Code", "value": str(check.status_code) if check.status_code else "N/A", "short": True},
                    {"title": "Latency", "value": f"{check.latency_ms:.0f}ms" if check.latency_ms else "N/A", "short": True},
                    {"title": "Error", "value": check.error_message or "None", "short": False},
                ],
                "ts": check.created_at.timestamp() if check.created_at else 0,
            }]
        }

        try:
            resp = requests.post(target.webhook_url, json=payload, timeout=10)
            log.info(f"Alert sent to {target.webhook_url}: {resp.status_code}")
        except Exception as e:
            log.error(f"Failed to send alert: {e}")
