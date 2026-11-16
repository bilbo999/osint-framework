# OSINT Framework

Framework modular para **analizar la exposición digital** de un objetivo (persona, organización,
dominio, IP, email, username, teléfono o URL) a partir de **fuentes públicas y APIs legítimas**.
Recopila, normaliza y correlaciona información, la representa como grafo y calcula un
**Exposure Score** (0–100) explicable, con trazabilidad completa de cada dato hasta su evidencia.

> **Estado:** Fase 1 de 13 — arquitectura, estructura y contratos base. Ver [docs/phases/](docs/phases/).

## Uso ético
Destinado a investigación OSINT, threat intelligence, análisis de exposición, auditorías
autorizadas, investigación académica y análisis de activos propios o autorizados. **No** realiza
intrusión, explotación, bypass de autenticación, credential stuffing, evasión de controles ni
acceso a información privada, y no debe usarse para doxxing. Ver [SPECS.md §33](docs/SPECS.md).

## Arquitectura
FastAPI + Pydantic + SQLAlchemy (PostgreSQL) · Neo4j (grafo) · arq/Redis (ejecución asíncrona) ·
React + TypeScript + Vite (UI) · Typer (CLI). Detalle y decisiones en
[docs/architecture.md](docs/architecture.md).

```text
backend/    API, servicios, collectors, análisis, scoring, grafo, informes (paquete `app`)
frontend/   React + TypeScript + Vite
config/     settings.yaml · collectors.yaml · scoring.yaml (sin secretos)
collectors/ plugins de collectors externos (descubrimiento automático)
docs/       especificación, arquitectura y plan por fases
scripts/    utilidades (check.sh)
docker/     Dockerfiles y configuración de servicios (Fase 13a)
```

## Inicio rápido (desarrollo)
Requisitos: [uv](https://docs.astral.sh/uv/) (instala Python 3.12 si falta) y Node.js ≥ 22.

```bash
cp .env.example .env                # rellena solo lo que necesites; nunca lo subas al repositorio
cd backend
uv sync
uv run uvicorn app.main:app --reload    # http://localhost:8000/api/v1/docs
uv run pytest -q

cd ../frontend
npm ci
npm run dev                             # http://localhost:5173
```

Comprobaciones de calidad: `scripts/check.sh` (ruff, black, mypy, pytest y build del frontend).

## Licencia
[MIT](LICENSE).
