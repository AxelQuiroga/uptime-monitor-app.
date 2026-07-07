"""
RQ Worker — processes individual target checks.
Horizontally scalable: docker compose up --scale worker=5

IMPORTANT: Runs as `python worker.py` (script, not module import).
The `import uptime.jobs` ensures RQ can resolve job function references.
"""
import uptime.jobs  # noqa: F401 — registers job functions for RQ resolution
from uptime.queue import redis_conn
from rq import Worker, Queue


def main():
    queue = Queue("uptime-checks", connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    print("[worker] RQ Worker started, waiting for jobs...", flush=True)
    worker.work()


if __name__ == "__main__":
    main()
