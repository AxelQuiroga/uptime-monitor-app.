# 📡 Uptime Monitor

Sistema de monitoreo de disponibilidad de servicios web. Verifica URLs periódicamente, registra histórico de respuestas, notifica cuando un servicio se cae, y expone un dashboard visual con el estado en tiempo real.

## 🏗️ Arquitectura

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   API        │     │   Checker    │     │     DB       │
│  Flask :5000 │     │  APScheduler │     │  PostgreSQL  │
│              │     │   c/30 seg   │     │              │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       └────────────────────┴────────────────────┘
                      │
              Docker Compose
              Red interna DNS

- **api** — Servidor Flask con API REST + dashboard HTML
- **checker** — Worker que verifica URLs cada 30 segundos
- **db** — PostgreSQL 16 con healthcheck y volumen persistente

## 🚀 Inicio Rápido

```bash
# Clonar
git clone https://github.com/AxelQuiroga/uptime-monitor.git
cd uptime-monitor

# Levantar todo
docker compose up -d --build

# Verificar que los 3 servicios estén UP
docker compose ps
📋 Endpoints de la API
Agregar URL a monitorear
curl -X POST http://localhost:5000/api/targets \
  -H "Content-Type: application/json" \
  -d '{"name":"Google","url":"https://google.com"}'
Ver estado de todos los targets
curl http://localhost:5000/api/status
Ver histórico de checks de un target
curl http://localhost:5000/api/history/1
Eliminar un target
curl -X DELETE http://localhost:5000/api/targets/1
Dashboard visual
Abrir en el navegador: http://localhost:5000
🖥️ Dashboard
Interfaz web con:
- Resumen — Total de targets, cuántos UP y DOWN
- Tarjetas — Cada target con su estado, código HTTP, latencia y timestamp
- Formulario — Agregar nuevos targets desde la web
- Eliminación — Botón para sacar targets del monitoreo
- Auto-refresh — Recarga manual con un click
🔔 Alertas por Webhook
Cuando un target cambia de UP a DOWN, el sistema envía una notificación a una URL configurable (Slack, Discord, o cualquier webhook).
curl -X POST http://localhost:5000/api/targets \
  -H "Content-Type: application/json" \
  -d '{"name":"Mi App","url":"https://miapp.com","webhook_url":"https://hooks.slack.com/..."}'
🐳 Servicios Docker
Servicio
API
Checker
PostgreSQL
🔄 Pipeline CI/CD
GitHub Actions verifica en cada push a main:
1. Checkout del código
2. Configura Python 3.12
3. Instala dependencias
4. Verifica imports de la app
5. Construye la imagen Docker
📁 Estructura del Proyecto
uptime-monitor/
├── uptime/
│   ├── __init__.py
│   ├── app.py              # Fábrica de Flask
│   ├── checker.py           # Verificador de URLs
│   ├── dashboard_routes.py  # Rutas del dashboard
│   ├── database.py          # Conexión a PostgreSQL
│   ├── models.py            # Modelos Target y Check
│   ├── notifier.py          # Alertas vía webhook
│   ├── routes.py            # API REST
│   └── templates/
│       └── dashboard.html   # Interfaz visual
├── .github/workflows/
│   └── ci.yml               # Pipeline CI
├── server.py                # Entry point API
├── runner.py                # Entry point checker
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
🛠️ Stack
Tecnología
Python 3.12
Flask
SQLAlchemy
APScheduler
Docker
Docker Compose
GitHub Actions
PostgreSQL 16
🧪 Desarrollo
Con volúmenes montados, los cambios en el código se reflejan al instante:
# Editar en VS Code, guardar, y recargar navegador
code .
Solo hace falta reconstruir cuando cambian dependencias:
docker compose down && docker compose up -d --build
📄 Licencia
MIT