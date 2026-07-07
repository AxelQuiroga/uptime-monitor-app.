---
name: uptime-test-infra
description: Configura la infraestructura de testing para uptime-monitor. Crea pytest setup, fixtures, base de datos de test, y tests para modelos, checker, notifier y API. Ejecutar ANTES de cualquier cambio arquitectónico.
---

# uptime-test-infra

## Propósito

Montar la infraestructura de testing desde cero. Este proyecto actualmente tiene **0 tests** y vamos a hacer cambios arquitectónicos profundos. Sin tests, no podemos garantizar que no rompemos nada.

## Stack de testing

- **pytest** + **pytest-flask** + **pytest-cov**
- SQLite **in-memory** para tests (rápido, no requiere PostgreSQL)
- Fixtures en `conftest.py` compartidas
- Coverage mínimo requerido post-setup: **60%+**

## Archivos a crear

```
uptime-monitor/
├── pytest.ini                 # Config de pytest
├── tests/
│   ├── conftest.py            # Fixtures globales (app, db, session, targets)
│   ├── test_models.py         # Tests de modelos (Target, Check)
│   ├── test_checker.py        # Tests de check_url
│   ├── test_notifier.py       # Tests de alertas
│   └── test_routes.py         # Tests de API REST
```

## 📋 Especificación de tests

### Fixtures (`conftest.py`)

```python
@pytest.fixture
def app():
    """Crea app Flask con SQLite in-memory para tests."""
    app = create_app()
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()

@pytest.fixture
def client(app):
    return app.test_client()

@pytest.fixture
def session(app):
    """Session de DB para manipular datos en tests."""
    with app.app_context():
        yield db.session

@pytest.fixture
def target(session):
    """Crea un target de prueba."""
    t = Target(name="Test", url="https://example.com", is_active=True)
    session.add(t)
    session.commit()
    return t
```

### test_models.py

| Test | Descripción |
|------|-------------|
| `test_create_target` | Crear Target, verificar campos default |
| `test_target_to_dict` | to_dict() devuelve estructura correcta |
| `test_target_unique_url` | Dos targets con misma URL → viola unique constraint |
| `test_create_check` | Crear Check asociado a Target |
| `test_check_to_dict` | to_dict() devuelve estructura correcta |
| `test_target_checks_relationship` | target.checks trae checks ordenados por fecha DESC |
| `test_check_default_values` | Check nuevo tiene valores default correctos |

### test_checker.py

| Test | Descripción |
|------|-------------|
| `test_check_url_success` | URL responde 200 → is_up=True, status_code, latency |
| `test_check_url_404` | URL responde 404 → is_up=False |
| `test_check_url_timeout` | URL no responde → is_up=False, error_message |
| `test_check_url_connection_error` | URL inexistente → ConnectionError → is_up=False |
| `test_check_url_creates_check_record` | check_url() guarda un Check en DB |
| `test_check_url_detects_status_change` | UP→DOWN → llama send_alert |
| `test_check_url_same_status_no_alert` | DOWN→DOWN → NO llama send_alert |
| `test_check_url_redirect_3xx` | 301 redirect → is_up=True (seguimos redirects) |
| `test_check_url_server_error_5xx` | 500 → is_up=False |

### test_notifier.py

Usar `responses` o `requests_mock` para mockear HTTP.

| Test | Descripción |
|------|-------------|
| `test_send_alert_down_transition` | UP→DOWN → envía webhook |
| `test_send_alert_up_transition` | DOWN→UP → envía webhook "recovered" |
| `test_send_alert_no_webhook` | Sin webhook → no envía nada |
| `test_send_alert_consecutive_down` | DOWN→DOWN → no spam |
| `test_send_alert_first_check_down` | None→DOWN → alerta con "FIRST_CHECK_DOWN" |
| `test_send_alert_first_check_up` | None→UP → no alerta |
| `test_send_alert_webhook_failure` | Webhook caído → loguea error, no crash |

### test_routes.py

| Test | Descripción |
|------|-------------|
| `test_list_targets_empty` | GET /api/targets → [] |
| `test_create_target` | POST /api/targets → 201 + target |
| `test_create_target_missing_url` | POST sin url → 400 |
| `test_create_target_duplicate` | POST misma url → 409 |
| `test_delete_target` | DELETE /api/targets/1 → 200 |
| `test_get_status` | GET /api/status → lista con status |
| `test_get_history` | GET /api/history/1 → lista de checks |

## Pytest config (`pytest.ini`)

```ini
[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*

# Plugins
#   pip install pytest pytest-flask pytest-cov
#   Run: python -m pytest --cov=uptime tests/
```

## Dependencias adicionales

Agregar a `requirements.txt` (o crear `requirements-dev.txt`):

```
# Testing
pytest>=7.4,<9
pytest-flask>=1.3
pytest-cov>=4.1
responses>=0.24
```

## Modo de ejecución

```bash
# Desde el container o local con venv
pip install -r requirements-dev.txt
python -m pytest tests/ -v
python -m pytest --cov=uptime tests/
```

## Criterios de aceptación

- ✅ `pytest tests/ -v` pasa todos los tests
- ✅ Coverage > 60% en módulos `uptime.*`
- ✅ Tests corren con SQLite in-memory (sin necesidad de PostgreSQL)
- ✅ Cada test es independiente (no depende del orden de ejecución)
- ✅ Mockeamos HTTP externo (no hacemos requests reales en tests)
