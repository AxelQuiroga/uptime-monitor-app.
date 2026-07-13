# 📡 Uptime Monitor

Distributed service health monitoring system. Checks URLs on configurable intervals, records response history, notifies on state changes via Slack/Discord/email, and exposes a public status page with uptime charts.

## 🏗️ Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   API        │     │  Scheduler   │     │   Worker(s)  │
│  Flask :5000 │     │  Polls DB    │────▶│  RQ + Redis  │
│  REST + Auth │     │  every 15s   │     │  HTTP checks │
└──────┬───────┘     └──────────────┘     └──────┬───────┘
       │                                         │
       │              ┌──────────┐               │
       └─────────────▶│ PostgreSQL│◀──────────────┘
                      │(TimescaleDB)│
                      └──────────┘
                            │
                      ┌──────────┐
                      │  Redis   │
                      │  (Queue) │
                      └──────────┘
```

- **API** — Flask server with REST endpoints, dashboard, and auth
- **Scheduler** — Polls every 15s for due targets, enqueues check jobs via Redis
- **Worker(s)** — RQ workers processing HTTP checks. Horizontally scalable: `docker compose up --scale worker=5`
- **PostgreSQL** — TimescaleDB hypertable with 90-day retention, continuous aggregates for hourly stats
- **Redis** — Message queue (RQ) for distributing check jobs across workers

## ✨ Features

- **Configurable monitoring** — Per-target check intervals (default 30s)
- **Real-time alerts** — Slack, Discord, and email notifications on state changes
- **Spam filtering** — No repeated alerts for targets that stay DOWN
- **Public status page** — Read-only overview with uptime % and latency charts (no auth required)
- **Private dashboard** — Full management panel with target CRUD and alert channel config
- **Aggregate reporting** — Hourly uptime %, avg/max/min latency via TimescaleDB continuous aggregates
- **Horizontal scaling** — Add more workers with a single flag
- **CI/CD** — GitHub Actions pipeline with PostgreSQL service container and test suite
- **Docker Compose** — 5 services, health checks, persistent volumes

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/AxelQuiroga/uptime-monitor-app.git
cd uptime-monitor-app

# Configure
cp .env.example .env
# Edit .env with your values (at minimum: SECRET_KEY, ADMIN_PASSWORD)

# Run migrations (TimescaleDB setup)
docker compose --profile setup run --rm migrate

# Start all services
docker compose up -d --build

# Verify all services are UP
docker compose ps
```

Open **http://localhost:5000** — public status page (no login needed).

Open **http://localhost:5000/dashboard** — management panel (login with `ADMIN_PASSWORD`).

## 📋 API Endpoints

### Targets

```bash
# Add a URL to monitor
curl -X POST http://localhost:5000/api/targets \
  -H "Content-Type: application/json" \
  -d '{"name":"Google","url":"https://google.com"}'

# List all targets
curl http://localhost:5000/api/targets

# Get current status
curl http://localhost:5000/api/status

# Get check history for a target
curl http://localhost:5000/api/history/1

# Get aggregate report (uptime %, latency stats)
curl http://localhost:5000/api/report/1?days=30

# Delete a target
curl -X DELETE http://localhost:5000/api/targets/1
```

### Alert Channels

```bash
# Add a Slack webhook
curl -X POST http://localhost:5000/api/alert-channels \
  -H "Content-Type: application/json" \
  -d '{"type":"slack","value":"https://hooks.slack.com/...","name":"Dev alerts"}'

# Add a Discord webhook
curl -X POST http://localhost:5000/api/alert-channels \
  -H "Content-Type: application/json" \
  -d '{"type":"discord","value":"https://discord.com/api/webhooks/..."}'

# Add email alerts
curl -X POST http://localhost:5000/api/alert-channels \
  -H "Content-Type: application/json" \
  -d '{"type":"email","value":"you@example.com"}'

# Toggle channel on/off
curl -X PATCH http://localhost:5000/api/alert-channels/1/toggle
```

### Public Status (no auth)

```bash
# Public status JSON
curl http://localhost:5000/api/public/status

# Public report with timeline
curl http://localhost:5000/api/public/report/1
```

## 🖥️ Dashboard

| Page | URL | Auth |
|------|-----|------|
| Public status | `/` | None |
| Target detail | `/target/<id>` | None |
| Management dashboard | `/dashboard` | Required |
| Login | `/login` | — |

## 🐳 Docker Services

| Service | Port | Description |
|---------|------|-------------|
| api | 5000 | Flask REST API + dashboard |
| scheduler | — | Polls DB for due targets, enqueues jobs |
| worker | — | RQ worker processing HTTP checks |
| redis | 6379 | Message queue backend |
| db | 5432 | PostgreSQL 16 + TimescaleDB |

Scale workers horizontally:

```bash
docker compose up -d --scale worker=3
```

## 🔄 CI/CD Pipeline

GitHub Actions runs on every push to `main`:

1. **Checkout** code
2. **Python 3.12** with pip cache
3. **Install** runtime + dev dependencies
4. **Run tests** — `pytest tests/ -v` (75 tests)
5. **Docker build** — verify image builds successfully

PostgreSQL service container runs in parallel for integration tests.

## 📁 Project Structure

```
uptime-monitor/
├── uptime/
│   ├── __init__.py
│   ├── app.py              # Flask app factory
│   ├── auth_routes.py      # Login/logout (Flask-Login)
│   ├── checker.py          # HTTP health check logic
│   ├── dashboard_routes.py # Management UI routes
│   ├── database.py         # SQLAlchemy config
│   ├── jobs.py             # RQ job functions
│   ├── models.py           # Target, Check, AlertChannel, AdminUser
│   ├── notifier.py         # Alert dispatcher + spam filter
│   ├── notifiers/          # Channel implementations
│   │   ├── slack.py
│   │   ├── discord.py
│   │   └── emailer.py
│   ├── queue.py            # Redis Queue config
│   ├── routes.py           # REST API endpoints
│   ├── status_routes.py    # Public status pages
│   └── templates/
│       ├── dashboard.html  # Management UI
│       ├── login.html      # Auth form
│       ├── status_detail.html   # Public target detail
│       └── status_public.html   # Public status overview
├── tests/
│   ├── conftest.py         # Fixtures (app, client, session)
│   ├── test_checker.py     # Health check logic
│   ├── test_migration.py   # DB migration
│   ├── test_models.py      # ORM models
│   ├── test_notifier.py    # Alert dispatching
│   ├── test_routes.py      # API endpoints
│   ├── test_scheduler.py   # Due-target polling
│   └── test_worker.py      # RQ worker jobs
├── .github/workflows/
│   └── ci.yml              # GitHub Actions pipeline
├── server.py               # Entry point: API
├── scheduler.py            # Entry point: scheduler
├── worker.py               # Entry point: RQ worker
├── migrate.py              # TimescaleDB migration
├── docker-compose.yml      # 5 services orchestration
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
├── .env.example
└── README.md
```

## 🛠️ Stack

| Technology | Purpose |
|------------|---------|
| Python 3.12 | Runtime |
| Flask | Web framework + REST API |
| SQLAlchemy | ORM |
| TimescaleDB (PostgreSQL 16) | Time-series storage with continuous aggregates |
| Redis | Job queue backend |
| RQ (Redis Queue) | Distributed task processing |
| Flask-Login | Session-based authentication |
| Docker / Docker Compose | Container orchestration |
| GitHub Actions | CI/CD pipeline |
| pytest | Test framework (75 tests) |

## 🧪 Development

With volumes mounted, code changes reflect instantly:

```bash
# Edit files, save, refresh browser
# Only rebuild when dependencies change:
docker compose down && docker compose up -d --build
```

Run tests locally:

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/ -v
```

## 📄 License

MIT
