"""
RQ job functions — must be importable for RQ worker to resolve.
RQ resolves function references via import, so these must live in an
importable module (not in __main__ like worker.py when run as script).
"""
from uptime.app import create_app
from uptime.models import Target, db
from uptime.checker import check_url

_app = None


def _get_app():
    """Lazy singleton: create Flask app once, reuse for all jobs."""
    global _app
    if _app is None:
        _app = create_app()
    return _app


def check_job(target_id: int):
    """Check a single target by ID. Runs inside an RQ worker."""
    app = _get_app()
    with app.app_context():
        target = db.session.get(Target, target_id)
        if not target:
            print(f"[worker] Target {target_id} not found, skipping", flush=True)
            return
        if not target.is_active:
            print(f"[worker] Target {target_id} inactive, skipping", flush=True)
            return
        result = check_url(target)
        status = "UP" if result.is_up else "DOWN"
        lat = f"{result.latency_ms:.0f}ms" if result.latency_ms else "N/A"
        print(f"[worker] [{status}] {target.url} - {lat}", flush=True)
        return result
