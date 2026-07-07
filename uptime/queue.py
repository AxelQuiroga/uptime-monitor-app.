"""Redis Queue configuration for uptime-monitor."""
import os
from redis import Redis
from rq import Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)

check_queue = Queue("uptime-checks", connection=redis_conn, default_timeout=60)
