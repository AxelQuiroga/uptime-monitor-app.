"""
TimescaleDB migration for uptime-monitor.
Idempotent — safe to run multiple times.
Standalone — no Flask dependency, uses raw SQL.

Run: docker compose --profile setup run migrate
"""
import os
from dotenv import load_dotenv

load_dotenv()


def run_migration():
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:secret123@localhost:5432/devopsdb"
    )

    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()

    print("[migrate] Connected")

    # 1. TimescaleDB extension
    cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
    print("[migrate] Extension ready")

    # 2. Create tables if they don't exist (standalone, no Flask needed)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS targets (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            url VARCHAR(500) NOT NULL UNIQUE,
            webhook_url VARCHAR(500),
            interval_seconds INTEGER DEFAULT 30,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS checks (
            id SERIAL PRIMARY KEY,
            target_id INTEGER NOT NULL REFERENCES targets(id),
            status_code INTEGER,
            latency_ms DOUBLE PRECISION,
            is_up BOOLEAN DEFAULT FALSE,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    """)
    print("[migrate] Tables ready")

    # 2.b Fix PK to include created_at (TimescaleDB requires partitioning col in PK)
    cur.execute("ALTER TABLE checks DROP CONSTRAINT IF EXISTS checks_pkey CASCADE;")
    cur.execute("ALTER TABLE checks ADD PRIMARY KEY (id, created_at);")
    print("[migrate] PK fixed to (id, created_at)")

    # 3. Convert checks to hypertable
    cur.execute("""
        SELECT * FROM create_hypertable('checks', 'created_at',
            if_not_exists => TRUE, migrate_data => TRUE);
    """)
    print("[migrate] Hypertable ready")

    # 4. Index on target_id + created_at
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_checks_target_time
        ON checks (target_id, created_at DESC);
    """)
    # 5. Index on created_at
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_checks_created_at
        ON checks (created_at DESC);
    """)
    print("[migrate] Indexes ready")

    # 6. Retention policy — 90 days
    cur.execute("""
        SELECT add_retention_policy('checks', INTERVAL '90 days',
            if_not_exists => TRUE);
    """)
    print("[migrate] Retention: 90 days")

    # 7. Continuous aggregate: hourly per-target
    cur.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_checks
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', created_at) AS bucket,
            target_id,
            COUNT(*) AS total_checks,
            COUNT(*) FILTER (WHERE is_up) AS up_checks,
            ROUND((COUNT(*) FILTER (WHERE is_up)::numeric / NULLIF(COUNT(*), 0) * 100), 2) AS uptime_pct,
            ROUND(AVG(latency_ms)::numeric, 2) AS avg_latency,
            ROUND(MAX(latency_ms)::numeric, 2) AS max_latency,
            ROUND(MIN(latency_ms)::numeric, 2) AS min_latency
        FROM checks
        GROUP BY bucket, target_id
        WITH NO DATA;
    """)
    print("[migrate] hourly_checks view created")

    # 8. Refresh policy for continuous aggregate
    cur.execute("""
        SELECT add_continuous_aggregate_policy('hourly_checks',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE);
    """)
    print("[migrate] Refresh policy ready")

    cur.close()
    conn.close()
    print("[migrate] Complete!")


if __name__ == "__main__":
    run_migration()
