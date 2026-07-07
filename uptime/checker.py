import requests
import time
from .models import Target, Check, db
from .notifier import send_alert

def check_url(target):
    start = time.time()
    # Buscamos el último check ANTES de hacer el nuevo (para detectar cambios)
    last_check = (
        Check.query
        .filter_by(target_id=target.id)
        .order_by(Check.created_at.desc())
        .first()
    )

    try:
        resp = requests.get(target.url, timeout=10, allow_redirects=True)
        latency = (time.time() - start) * 1000
        is_up = 200 <= resp.status_code < 400
        check = Check(target_id=target.id, status_code=resp.status_code, latency_ms=latency, is_up=is_up)
    except requests.ConnectionError:
        check = Check(target_id=target.id, status_code=None, latency_ms=None, is_up=False, error_message="Connection failed")
    except requests.Timeout:
        check = Check(target_id=target.id, status_code=None, latency_ms=None, is_up=False, error_message="Timeout after 10s")
    except Exception as e:
        check = Check(target_id=target.id, status_code=None, latency_ms=None, is_up=False, error_message=str(e))

    db.session.add(check)
    db.session.commit()

    # Notificar si cambió el estado
    previous_up = last_check.is_up if last_check else None  # None = primera vez, no sabemos estado anterior
    if previous_up != check.is_up:
        send_alert(target, check, previous_up)

    return check
