"""
RQ Worker — processes individual target checks.
Horizontally scalable: docker compose up --scale worker=5
"""
import os
import sys
from uptime.app import create_app
from uptime.models import Target, db
from uptime.checker import check_url
from uptime.queue import redis_conn
from rq import Worker, Queue

def check_job(target_id: int):
    """Check a single target by ID. Runs inside an RQ worker."""
    app = create_app()
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

def main():
    queue = Queue("uptime-checks", connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    print("[worker] RQ Worker started, waiting for jobs...", flush=True)
    worker.work()

if __name__ == "__main__":
    main()
