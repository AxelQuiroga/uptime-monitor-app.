"""
Scheduler — polls for due targets and enqueues check jobs.
Replaces the old APScheduler-based runner.py.
"""
import os
import time
import sys
from datetime import datetime, timezone
from uptime.app import create_app
from uptime.models import Target, Check
from uptime.queue import check_queue

POLL_INTERVAL = 15

def get_due_targets():
    """Return active targets whose next check is overdue."""
    app = create_app()
    with app.app_context():
        now = datetime.now(timezone.utc)
        targets = Target.query.filter_by(is_active=True).all()
        due = []
        for target in targets:
            last_check = (
                Check.query
                .filter_by(target_id=target.id)
                .order_by(Check.created_at.desc())
                .first()
            )
            if last_check:
                check_time = last_check.created_at
                if check_time.tzinfo is None:
                    check_time = check_time.replace(tzinfo=timezone.utc)
                elapsed = (now - check_time).total_seconds()
                if elapsed < target.interval_seconds:
                    continue
            due.append(target)
        return due

def enqueue_checks(targets):
    for target in targets:
        check_queue.enqueue(
            "uptime.worker.check_job",
            target.id,
            job_timeout=target.interval_seconds,
            description=f"check:{target.id}:{target.url}"
        )

def main():
    print(f"[scheduler] Started (poll every {POLL_INTERVAL}s)", flush=True)
    sys.stdout.flush()
    while True:
        try:
            due = get_due_targets()
            if due:
                print(f"[scheduler] Enqueuing {len(due)} checks", flush=True)
                enqueue_checks(due)
        except Exception as e:
            print(f"[scheduler] Error: {e}", flush=True)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
