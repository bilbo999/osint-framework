# Fase 13a: Docker y entorno de un solo comando

## Objetivo
Levantar todo el sistema con `docker compose up --build` (frontend, backend, worker, postgres, neo4j,
redis) con healthchecks, migraciones automáticas, credenciales de desarrollo documentadas y modo demo
activable sin credenciales reales (SPECS.md §26–27).

## Dependencias (fases previas y contratos que usa)
- Fases 1–12 (backend, worker arq, migraciones Alembic, frontend build, demo loader).
- `docker-compose.yml` parcial creado en Fases 2 y 6; `.env.example` (Fase 1).

## Archivos a crear o modificar (rutas exactas)
- `docker/backend.Dockerfile`: multi-stage (`uv` para resolver `uv.lock`), Python 3.12-slim, extra `pdf`
  con dependencias de sistema de WeasyPrint (Pango), usuario no root, `HEALTHCHECK` contra `/api/v1/health`.
- `docker/frontend.Dockerfile`: build con Node LTS + `npm ci`, runtime `nginx:alpine` sirviendo `dist/`.
- `docker/nginx.conf`: SPA fallback, proxy `/api/` → `backend:8000`, cabeceras de seguridad (CSP, HSTS
  desactivado en local, `X-Content-Type-Options`, `Referrer-Policy`).
- `docker/entrypoint-backend.sh`: espera a postgres, `alembic upgrade head`, arranca uvicorn.
- `docker-compose.yml`: servicios `postgres`, `neo4j`, `redis`, `backend`, `worker` (misma imagen,
  `arq app.workers.settings.WorkerSettings`), `frontend`; volúmenes nombrados; red interna; `depends_on`
  con `condition: service_healthy`; config montada en `/app/config` (`OSINT_CONFIG_DIR=/app/config`).
- `docker-compose.override.example.yml`: hot reload para desarrollo (montajes de código).
- `.dockerignore` (raíz, `backend/`, `frontend/`): excluir `.env`, `node_modules`, `.venv`, `var/`, cachés.
- `.env.example`: revisar que contiene todas las variables usadas por compose.
- Tests: `backend/tests/unit/test_compose_config.py` (parsea el YAML y valida servicios/healthchecks/puertos).

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-002: worker separado del backend con la misma imagen.
- ADR-004: Neo4j puede tardar más en arrancar; el backend no depende de él para estar *healthy* (readiness degradada).
- ADR-010: `OSINT_DEMO_MODE=true docker compose up --build` + `docker compose exec backend osint demo load`.
- Credenciales de desarrollo solo como valores por defecto **de compose** marcados `dev-only`
  (`${POSTGRES_PASSWORD:-osint-dev-only-change-me}`), nunca en el código Python ni en las imágenes.
- Solo `frontend` (8080) expone puerto al host por defecto; backend 8000, Neo4j 7474/7687, Postgres 5432
  y Redis 6379 se publican únicamente en `127.0.0.1` para desarrollo.

## Interfaces y firmas clave (código)
```yaml
# docker-compose.yml (forma esperada, abreviada)
services:
  postgres: { image: postgres:17-alpine, healthcheck: { test: ["CMD-SHELL", "pg_isready -U $${POSTGRES_USER}"] } }
  redis:    { image: redis:7-alpine, healthcheck: { test: ["CMD", "redis-cli", "ping"] } }
  neo4j:    { image: neo4j:5-community, environment: { NEO4J_AUTH: "neo4j/${NEO4J_PASSWORD:-osint-dev-only-change-me}" } }
  backend:  { build: { context: ., dockerfile: docker/backend.Dockerfile }, depends_on: { postgres: { condition: service_healthy } } }
  worker:   { image: osint-backend, command: ["arq", "app.workers.settings.WorkerSettings"] }
  frontend: { build: { context: ., dockerfile: docker/frontend.Dockerfile }, ports: ["8080:80"] }
```
| Servicio | URL local | Credenciales de desarrollo |
|---|---|---|
| Frontend | http://localhost:8080 | usuario creado con `osint admin create-user` |
| API / Swagger | http://127.0.0.1:8000/api/v1/docs | — |
| Neo4j Browser | http://127.0.0.1:7474 | `neo4j` / `NEO4J_PASSWORD` |
| PostgreSQL | 127.0.0.1:5432 | `POSTGRES_USER` / `POSTGRES_PASSWORD` |

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- `test_compose_config.py`: los 6 servicios existen, todos con healthcheck, ninguno con secretos
  literales distintos de los marcados `dev-only`, volúmenes nombrados para datos, `worker` usa arq.
- Manual/CI (job opcional con Docker): `docker compose up -d --build --wait` y `curl` a health y frontend.
- Imagen backend: ejecuta como usuario no root (`docker compose exec backend id -u` ≠ 0).

## Criterios de aceptación verificables (comandos concretos)
```bash
cp .env.example .env            # opcional: compose tiene valores dev-only por defecto
docker compose up --build -d --wait
curl -fs http://127.0.0.1:8000/api/v1/health && curl -fs http://localhost:8080/ >/dev/null
docker compose exec backend osint admin create-user --email admin@example.org --role admin
OSINT_DEMO_MODE=true docker compose up -d && docker compose exec backend osint --local demo load
docker compose down -v
cd backend && uv run pytest tests/unit/test_compose_config.py -q
```

## Fuera de alcance
Kubernetes/Helm, TLS real, backups automatizados, despliegue en la nube (solo notas en la doc de seguridad).

## Riesgos y trampas conocidas
- Fin de línea CRLF en `entrypoint-backend.sh` desde Windows rompe el contenedor: `.gitattributes` con `*.sh text eol=lf`.
- Neo4j necesita memoria: fijar `NEO4J_server_memory_heap_max__size=512m` en local.
- `uv sync --frozen` en la imagen: el `uv.lock` debe estar actualizado (fallará si no).
- No copiar `.env` a la imagen; las variables llegan por `env_file`/`environment` en runtime.
