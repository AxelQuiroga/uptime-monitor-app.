---
name: uptime-rq-worker
description: Reemplaza APScheduler por Redis Queue (RQ) con workers horizontales escalables. Implementa scheduler polling + workers independientes + per-target scheduling respetando interval_seconds. Ejecutar DESPUÉS de uptime-test-infra.
---

# uptime-rq-worker

## Contexto del proyecto

- Python 3.12, Flask, Flask-SQLAlchemy, PostgreSQL
- Modelos: Target (id, name, url, webhook_url, interval_seconds, is_active, created_at) y Check (id, target_id FK, status_code, latency_ms, is_up, error_message, created_at)
- checker.py: `check_url(target)` que hace HTTP request, guarda Check en DB, llama a `send_alert(target, check, previous_up)`
- runner.py: APScheduler BlockingScheduler cada 30s checkea TODOS los targets secuencialmente
- Tests existentes: 39 tests en tests/ (pytest, SQLite in-memory, responses library)

## Decisiones arquitectónicas (ya aprobadas)

| Decisión | Opción elegida | Alternativa descartada |
|----------|---------------|----------------------|
| Scheduler | Polling cada 15s. Pregunta qué targets están listos y encola | Event-driven (más complejo, frágil) |
| Workers | Usan `create_app()` con Flask app context | SQLAlchemy directa (duplica config) |
| Cola | **RQ** (Redis Queue) — simple, liviano, escalable | Celery (overkill) |

## Arquitectura

```
scheduler.py (1 pod)
  │
  │ Cada 15s: Target.query.filter_by(is_active=True)
  │     └── ¿último_check + interval_seconds > ahora? → queue.enqueue(check_job, target.id)
  │
  ▼
┌─────────┐
│  Redis  │  Queue: "uptime-checks"
└────┬────┘
     │
     │  RQ Workers (N pods, docker compose up --scale worker=N)
     ▼
worker.py
  │
  ├── create_app() → app context
  ├── Target.query.get(target_id)
  ├── check_url(target)  ← lógica EXISTENTE (se reusa)
  └── Guarda Check, alerta si cambia
```

## Archivos a crear

### 1. scheduler.py (Remplaza a runner.py)

```python
"""
Scheduler de uptime-monitor.
Encola checks en Redis Queue para que los workers los procesen.
Corre como un proceso único.
"""
import os
import time
from datetime import datetime, timezone
from uptime.app import create_app
from uptime.models import Target, Check
from uptime.queue import check_queue

POLL_INTERVAL = 15  # segundos entre cada ciclo de planificación

def get_due_targets():
    """Devuelve targets activos cuyo próximo check ya venció."""
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
                elapsed = (now - last_check.created_at).total_seconds()
                if elapsed < target.interval_seconds:
                    continue  # Todavía no le toca
            due.append(target)
        return due

def enqueue_checks(targets):
    """Encola un job por target en Redis Queue."""
    for target in targets:
        check_queue.enqueue(
            "uptime.worker.check_job",           # función a ejecutar
            target.id,                            # argumento
            job_timeout=target.interval_seconds,  # timeout máximo
            description=f"check:{target.id}:{target.url}"
        )

def main():
    print(f"[scheduler] Started (poll every {POLL_INTERVAL}s)")
    while True:
        try:
            due = get_due_targets()
            if due:
                print(f"[scheduler] Enqueuing {len(due)} checks")
                enqueue_checks(due)
            else:
                print(f"[scheduler] No targets due")
        except Exception as e:
            print(f"[scheduler] Error: {e}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
```

### 2. worker.py (NUEVO)

```python
"""
RQ Worker para uptime-monitor.
Procesa checks de targets individuales.
Escalable horizontalmente: docker compose up --scale worker=5
"""
import os
from uptime.app import create_app
from uptime.models import Target, db
from uptime.checker import check_url
from uptime.queue import redis_conn
from rq import Worker, Queue

def check_job(target_id: int):
    """Procesa el check de UN target. Ejecutado por RQ Worker."""
    app = create_app()
    with app.app_context():
        target = db.session.get(Target, target_id)
        if not target:
            print(f"[worker] Target {target_id} not found, skipping")
            return
        if not target.is_active:
            print(f"[worker] Target {target_id} is inactive, skipping")
            return
        result = check_url(target)
        status = "UP" if result.is_up else "DOWN"
        lat = f"{result.latency_ms:.0f}ms" if result.latency_ms else "N/A"
        print(f"[worker] [{status}] {target.url} - {lat}")
        return result

def main():
    queue = Queue("uptime-checks", connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)
    print("[worker] RQ Worker started, waiting for jobs...")
    worker.work()

if __name__ == "__main__":
    main()
```

### 3. uptime/queue.py (NUEVO)

```python
"""
Configuración de Redis Queue para uptime-monitor.
"""
import os
from redis import Redis
from rq import Queue

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_conn = Redis.from_url(REDIS_URL)

# Cola principal para checks de uptime
check_queue = Queue("uptime-checks", connection=redis_conn, default_timeout=60)
```

## Archivos a modificar

### 4. docker-compose.yml

Agregar servicios:

```yaml
services:
  # ... api, db existentes ...

  scheduler:
    build: .
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://redis:6379/0
      - PYTHONUNBUFFERED=1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    command: python scheduler.py

  worker:
    build: .
    volumes:
      - .:/app
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - REDIS_URL=redis://redis:6379/0
      - PYTHONUNBUFFERED=1
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_started
    command: python worker.py

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  uptime-pgdata:
```

### 5. runner.py

**ELIMINAR** este archivo. Su función la toma scheduler.py + worker.py.

### 6. requirements.txt

Agregar:
```
rq>=1.16,<3
redis>=5.0,<6
```

### 7. tests/test_checker.py

- La lógica de `check_url()` NO cambia — solo se modifica CÓMO se llama
- Los tests existentes de `check_url(target)` deberían seguir pasando SIN cambios
- SOLO verificar que los imports sigan funcionando

Agregar NUEVOS tests:

### 8. tests/test_scheduler.py (NUEVO)

```python
"""Tests para scheduler.py — NO requiere Redis real, mockea la cola."""

# Test: get_due_targets con target vencido
# Test: get_due_targets con target NO vencido (interval no cumplido)
# Test: get_due_targets con target sin historial (nuevo, siempre debe checkearse)
# Test: enqueue_checks llama a check_queue.enqueue por cada target
```

### 9. tests/test_worker.py (NUEVO)

```python
"""Tests para worker.py — mockea Redis y la DB."""

# Test: check_job con target activo → ejecuta check_url
# Test: check_job con target inactivo → NO ejecuta check_url
# Test: check_job con target inexistente → loguea warning, no crash
```

## Dependencias de test adicionales

Agregar a `requirements-dev.txt`:
```
fakeredis>=2.23,<3    # Mock de Redis para tests
```

## Integration notes

- Redis NO necesita persistencia (es solo cola transitoria). Si Redis se cae, los jobs se pierden PERO el scheduler los re-encola en el próximo ciclo.
- `PYTHONUNBUFFERED=1` en los containers para ver logs en tiempo real
- Los workers deben poder escribir en la misma DB que la API
- NO hay migraciones de DB en este paso — solo agregamos servicios

## Criterios de aceptación

- ✅ `pytest tests/ -v` — todos los tests pasan (incluyendo nuevos)
- ✅ `docker compose up --build` levanta sin errores
- ✅ `docker compose up --scale worker=3` levanta 3 workers
- ✅ Worker puede conectarse a Redis
- ✅ Worker puede conectarse a PostgreSQL y leer/escribir Checks
- ✅ Scheduler encola jobs y workers los procesan
- ✅ Se respeta `interval_seconds` por target (no se checkea antes de tiempo)
