---
name: uptime-code-auditor
description: Escanea la codebase de uptime-monitor buscando code quality issues, hardcoded secrets, errores lógicos, deuda técnica, y falta de types. Ejecutar ANTES y DESPUÉS de cada paso de transformación para verificar que no se introduce regresión.
---

# uptime-code-auditor

## Propósito

Auditar el código fuente de `uptime-monitor` y producir un reporte estructurado de hallazgos. Se ejecuta en dos modos:

- **PRE-audit**: antes de empezar un paso, para saber el estado actual
- **POST-audit**: después de un paso, para verificar que no se introdujeron nuevos problemas

## Qué revisar

### 1. 🔒 Hardcoded Secrets
Buscar en TODOS los archivos `.py`, `.yml`, `.sh`:
- Passwords en texto plano (`secret123`, `password=`, `pass:`)
- API keys, tokens, secrets
- Connection strings con credenciales
- URLs con credenciales embedidas (`user:pass@host`)

### 2. 🐛 Errores lógicos potenciales
- Comparaciones que deberían considerar `None`
- Assunciones incorrectas (ej: asumir que un query siempre devuelve algo)
- Variables usadas antes de ser asignadas
- Excepciones capturadas genéricamente (`except Exception`) sin logging adecuado
- Retornos inconsistentes (a veces dict, a veces None, a veces string)

### 3. 🏗️ Deuda técnica
- Falta de type hints en funciones y métodos
- Docstrings faltantes
- Código comentado
- Imports no utilizados
- Funciones muy largas (>30 líneas)
- Lógica duplicada

### 4. ⚠️ Problemas de concurrencia
- Estado compartido sin locks
- Operaciones no atómicas en la DB
- Race conditions potenciales

### 5. 📦 Dependencias
- Versiones pinned vs flexibles
- Dependencias no utilizadas en `requirements.txt`
- Vulnerabilidades conocidas

## Output

Generar un reporte estructurado con:

```json
{
  "audit_id": "pre-{nombre-del-paso}-{timestamp}",
  "phase": "pre | post",
  "step": "nombre del paso",
  "summary": {
    "critical": 0,
    "warning": 0,
    "info": 0,
    "total": 0
  },
  "findings": [
    {
      "severity": "critical | warning | info",
      "file": "uptime/models.py",
      "line": 42,
      "code": "HARDCODED_SECRET",
      "title": "título corto",
      "description": "descripción detallada",
      "suggestion": "cómo arreglarlo"
    }
  ]
}
```

## Códigos de hallazgo

| Código | Severidad | Significado |
|--------|-----------|-------------|
| `HARDCODED_SECRET` | critical | Password, token o secret en texto plano |
| `LOGIC_ERROR` | critical | Bug potencial que puede causar comportamiento incorrecto |
| `MISSING_TYPE_HINTS` | warning | Función sin type hints |
| `BROAD_EXCEPT` | warning | `except Exception:` sin logging o manejo específico |
| `NO_DOCSTRING` | info | Función pública sin docstring |
| `UNUSED_IMPORT` | info | Import que no se usa |
| `LONG_FUNCTION` | info | Función > 30 líneas |
| `DUPLICATE_CODE` | warning | Lógica duplicada en 2+ lugares |
| `RACE_CONDITION` | critical | Condición de carrera potencial |
| `MAGIC_NUMBER` | info | Número mágico sin constante nominal |
| `PINNED_DEP` | info | Dependencia pinned sin rango de versión |
