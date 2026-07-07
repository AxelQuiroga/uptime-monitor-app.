import requests
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("notifier")

def send_alert(target, check, previous_up):
    """Manda alerta si el estado cambió de UP a DOWN (o viceversa).

    Args:
        target: El Target monitoreado.
        check: El Check que se acaba de realizar.
        previous_up: True si el último check estaba UP,
                     False si estaba DOWN,
                     None si es la primera vez (no hay historial).
    """
    if not target.webhook_url:
        log.info(f"No webhook configured for {target.name}, skipping alert")
        return

    # --- Filtros de spam ---
    if previous_up is False and not check.is_up:
        # Ya estaba DOWN, sigue DOWN — no spam
        return

    if previous_up is None and check.is_up:
        # Primera vez y está UP — no hay nada que notificar
        return

    # --- Determinar tipo de transición ---
    if previous_up is None:
        # Primera vez, está DOWN
        event_type = "FIRST_CHECK_DOWN"
        status = "DOWN"
        color = "red"
        title = f"[DOWN] {target.name} (nuevo target)"
    elif previous_up and not check.is_up:
        event_type = "DOWN"
        status = "DOWN"
        color = "red"
        title = f"[DOWN] {target.name}"
    elif not previous_up and check.is_up:
        event_type = "UP"
        status = "UP"
        color = "green"
        title = f"[UP] {target.name} — recovered"
    else:
        # Mismo estado, no alertar
        return

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
        log.info(f"Alert sent to {target.webhook_url}: {resp.status_code}")
    except requests.ConnectionError:
        log.error(f"Failed to connect to webhook {target.webhook_url}")
    except requests.Timeout:
        log.error(f"Timeout sending alert to {target.webhook_url}")
    except Exception as e:
        log.error(f"Failed to send alert: {e}")
