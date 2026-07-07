---
name: uptime-timescale
description: Migra la tabla checks a TimescaleDB hypertable con retention de 90 días, continuous aggregates para reports, y nuevos endpoints de API para consultar uptime y latencia. Ejecutar DESPUÉS de uptime-rq-worker.
---

# uptime-timescale

## Decisiones arquitectónicas (ya aprobadas)

| Decisión | Opción elegida |
|----------|---------------|
| Image DB | `timescale/timescaledb:latest-pg16` |
| Migración | Script `migrate.py` ejecutado como comando único de Docker |
| Retention | 90 días, automática via TimescaleDB |
| Continuous aggregates | `hourly_checks` — bucket 1h, uptime%, avg/max latencia |
| API reports | `GET /api/report/<id>?days=30` y `GET /api/report/<id>/timeline` |

## Archivos a crear

### 1. uptime/migration.py

Script de migración idempotente. Verifica si la hypertable ya existe antes de crear.

```python
"""
TimescaleDB migration for uptime-monitor.
Idempotent — safe to run multiple times.
Run: python migrate.py
"""
import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Allow running standalone
load_dotenv()

def run_migration():
    """Create hypertable, set retention, create continuous aggregates."""
    import psycopg2
    from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

    DATABASE_URL = os.getenv(
        "DATABASE_URL",
        "postgresql://admin:secret123@localhost:5432/devopsdb"
    )
    
    conn = psycopg2.connect(DATABASE_URL)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cur = conn.cursor()
    
    print("[migrate] Connected to database")
    
    # 1. Ensure TimescaleDB extension
    cur.execute("CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;")
    print("[migrate] TimescaleDB extension ready")
    
    # 2. Convert checks to hypertable (idempotent)
    cur.execute("""
        SELECT * FROM create_hypertable('checks', 'created_at',
            if_not_exists => TRUE,
            migrate_data => TRUE);
    """)
    print("[migrate] Hypertable 'checks' ready")
    
    # 3. Add index on target_id + created_at for fast queries
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_checks_target_time
        ON checks (target_id, created_at DESC);
    """)
    print("[migrate] Index idx_checks_target_time ready")
    
    # 4. Index on created_at for time-range queries
    cur.execute("""
        CREATE INDEX IF NOT EXISTS idx_checks_created_at
        ON checks (created_at DESC);
    """)
    print("[migrate] Index idx_checks_created_at ready")
    
    # 5. Retention policy — 90 days
    cur.execute("""
        SELECT add_retention_policy('checks', INTERVAL '90 days',
            if_not_exists => TRUE);
    """)
    print("[migrate] Retention policy set: 90 days")
    
    # 6. Continuous aggregate: hourly per-target stats
    cur.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS hourly_checks
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', created_at) AS bucket,
            target_id,
            COUNT(*) AS total_checks,
            COUNT(*) FILTER (WHERE is_up) AS up_checks,
            ROUND((COUNT(*) FILTER (WHERE is_up)::numeric / NULLIF(COUNT(*), 0) * 100), 2) AS uptime_pct,
            ROUND(AVG(latency_ms), 2) AS avg_latency,
            ROUND(MAX(latency_ms), 2) AS max_latency,
            ROUND(MIN(latency_ms), 2) AS min_latency
        FROM checks
        GROUP BY bucket, target_id
        WITH NO DATA;
    """)
    print("[migrate] Materialized view 'hourly_checks' created")
    
    # 7. Add refresh policy for continuous aggregate
    cur.execute("""
        SELECT add_continuous_aggregate_policy('hourly_checks',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour',
            if_not_exists => TRUE);
    """)
    print("[migrate] Continuous aggregate policy set: refresh every 1h")
    
    cur.close()
    conn.close()
    print("[migrate] Migration complete!")

if __name__ == "__main__":
    run_migration()
```

⚠️ **IMPORTANTE**: Este script usa `psycopg2` directamente (no Flask-SQLAlchemy) porque se ejecuta fuera de la app. Agregar a `requirements.txt`: `psycopg2-binary>=2.9,<3` (ya existe) y `python-dotenv>=1.0`.

### 2. tests/test_migration.py

```python
"""Tests para migrate.py — solo verifica que el script no crashee y que sea idempotente."""
# Nota: estos tests requieren PostgreSQL + TimescaleDB, no SQLite.
# Se marcan con @pytest.mark.skipif para que no corran en CI sin PostgreSQL.
```

## Archivos a modificar

### 3. docker-compose.yml

Cambiar:
```yaml
db:
  image: timescale/timescaledb:latest-pg16  # en vez de postgres:16-alpine
```

Y agregar service `migrate`:
```yaml
migrate:
  build: .
  environment:
    - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
  depends_on:
    db:
      condition: service_healthy
  command: python uptime/migration.py
  profiles:
    - setup  # corre manual: docker compose --profile setup run migrate
```

### 4. uptime/routes.py

Agregar ENDPOINTS NUEVOS:

**GET /api/report/<target_id>**
```python
@api.route("/report/<int:target_id>")
def get_report(target_id):
    """Uptime report for a target over the last N days."""
    days = request.args.get("days", 30, type=int)
    target = Target.query.get_or_404(target_id)
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    # Query from continuous aggregate (fast!)
    hourly = db.session.execute(
        text("""
            SELECT
                COALESCE(SUM(total_checks), 0) AS total_checks,
                COALESCE(SUM(up_checks), 0) AS up_checks,
                ROUND(COALESCE(AVG(uptime_pct), 0), 2) AS uptime_pct,
                ROUND(COALESCE(AVG(avg_latency), 0), 2) AS avg_latency,
                ROUND(COALESCE(MAX(max_latency), 0), 2) AS max_latency,
                ROUND(COALESCE(MIN(min_latency), 0), 2) AS min_latency
            FROM hourly_checks
            WHERE target_id = :tid AND bucket >= :since
        """),
        {"tid": target_id, "since": since}
    ).fetchone()
    
    return jsonify({
        "target_id": target_id,
        "target_name": target.name,
        "target_url": target.url,
        "days": days,
        "since": since.isoformat(),
        "total_checks": hourly[0],
        "up_checks": hourly[1],
        "uptime_pct": hourly[2],
        "avg_latency_ms": hourly[3],
        "max_latency_ms": hourly[4],
        "min_latency_ms": hourly[5],
    })
```

**GET /api/report/<target_id>/timeline**
```python
@api.route("/report/<int:target_id>/timeline")
def get_timeline(target_id):
    """Time-series data for charts."""
    days = request.args.get("days", 7, type=int)
    target = Target.query.get_or_404(target_id)
    
    since = datetime.now(timezone.utc) - timedelta(days=days)
    
    rows = db.session.execute(
        text("""
            SELECT
                bucket,
                total_checks,
                up_checks,
                uptime_pct,
                avg_latency,
                max_latency,
                min_latency
            FROM hourly_checks
            WHERE target_id = :tid AND bucket >= :since
            ORDER BY bucket ASC
        """),
        {"tid": target_id, "since": since}
    ).fetchall()
    
    return jsonify({
        "target_id": target_id,
        "target_name": target.name,
        "days": days,
        "timeline": [
            {
                "bucket": row[0].isoformat() if row[0] else None,
                "total_checks": row[1],
                "up_checks": row[2],
                "uptime_pct": row[3],
                "avg_latency_ms": row[4],
                "max_latency_ms": row[5],
                "min_latency_ms": row[6],
            }
            for row in rows
        ]
    })
```

Importar en routes.py: `from datetime import datetime, timezone, timedelta` y `from sqlalchemy import text`.

### 5. uptime/templates/dashboard.html

Agregar en cada card de target un link o botón "Report →" que lleve a `GET /api/report/<id>` (o mostrar un mini-resumen de uptime en la card).

## Criterios de aceptación

- ✅ `docker compose up -d db` → levanta TimescaleDB (no PostgreSQL vanilla)
- ✅ `docker compose --profile setup run migrate` → migración exitosa, idempotente
- ✅ `pytest tests/ -v` — tests existentes siguen pasando
- ✅ `curl /api/report/1?days=30` → devuelve JSON con uptime_pct, avg_latency, etc.
- ✅ `curl /api/report/1/timeline?days=7` → devuelve array de buckets horarios
