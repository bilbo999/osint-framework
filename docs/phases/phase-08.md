# Fase 8: API REST completa + autenticación + auditoría

## Objetivo
Exponer todos los recursos de SPECS.md §17 bajo `/api/v1`, documentados en OpenAPI, con
autenticación, autorización por rol, sesiones, CSRF, rate limiting, logs de auditoría, gestión de
collectors (activar/desactivar, timeouts, rate limits, API keys cifradas) y `/metrics`.

## Dependencias (fases previas y contratos que usa)
- Fase 2: `InvestigationService`, repositorios, UoW. Fase 3: `JobQueue`, `InvestigationOrchestrator.progress`.
- Fase 5: entidades/relaciones. Fase 6: `GraphQueryService`, export. Fase 7: `ExposureScore`, `ConfidenceBreakdown`.
- Fase 1: `settings.security`, `CollectorRegistry.metadata()`, `CollectorsConfig.resolve`.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/core/security.py`: hashing argon2id, tokens, CSRF, cifrado Fernet.
- `backend/app/models/{user,session,api_token,collector_override,collector_secret}.py` + migración `0003_auth_and_overrides.py`.
- `backend/app/services/{auth,users,collector_admin,exports}.py`.
- `backend/app/api/deps.py`: `get_current_user`, `require_role(...)`, `get_uow`, paginación.
- `backend/app/api/errors.py`: excepciones de dominio ⇒ `application/problem+json` (RFC 9457).
- `backend/app/api/middleware.py`: CSRF, rate limit (Redis; memoria en tests), request-id, cabeceras de seguridad.
- `backend/app/api/v1/{auth,investigations,targets,findings,entities,relationships,graph,scores,reports,collectors,evidence,audit}.py`
  y `backend/app/api/v1/router.py` (incluirlos). `GET /metrics` en `backend/app/main.py`.
- `backend/app/schemas/{common,auth,investigation,target,finding,entity,relationship,graph,score,report,collector,evidence}.py`.
- `backend/app/cli/admin.py`: `osint admin create-user` (único comando que usa servicios directamente: bootstrap).
- Tests: `backend/tests/unit/api/test_<recurso>.py`, `test_auth.py`, `test_csrf.py`, `test_rate_limit.py`,
  `test_problem_details.py`, `test_openapi.py`; `backend/tests/integration/test_api_postgres.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-005: sesión opaca en cookie + CSRF; tokens `osk_` para CLI (cabecera `Authorization: Bearer`); roles.
- ADR-011: la CLI consumirá exactamente estos endpoints.
- ADR-013: auditoría de toda operación mutante y de login (éxito/fallo) en `audit_log` (sin secretos).
- Overrides de collectors guardados en `collector_overrides` y fusionados **sobre** `collectors.yaml`.
- API keys: `PUT /collectors/{name}/api-key` cifra con Fernet; `GET` solo devuelve `{configured, last4, source: env|db}`.
- Paginación `?limit=&offset=` (máx 500) con `{items, total, limit, offset}`. Fechas ISO 8601 UTC.
- Toda respuesta con datos de una investigación sintética incluye `is_synthetic: true`.

## Interfaces y firmas clave (código)
Endpoints (además de `/health`, `/health/ready`):
```text
POST /auth/login | POST /auth/logout | GET /auth/me | POST /auth/tokens | DELETE /auth/tokens/{id}
GET|POST /investigations      GET|PATCH|DELETE /investigations/{id}
POST /investigations/{id}/duplicate | /close | /reopen | /scan {collectors?: [...]}
GET  /investigations/{id}/progress   GET /investigations/{id}/export (JSON completo)
GET|POST /targets?investigation_id=   GET|DELETE /targets/{id}
GET  /findings?investigation_id=&type=&min_confidence=&provenance=&source=   GET /findings/{id} (incl. evidence + confidence_factors)
GET  /evidence/{id}                   GET /entities?investigation_id=&type=   GET /entities/{id}
GET  /relationships?investigation_id=&type=&min_confidence=   GET /relationships/{id}
GET  /graph/{investigation_id}?types=&min_confidence=&limit=  GET /graph/{investigation_id}/neighbors/{entity_id}?depth=
GET  /graph/{investigation_id}/path?from=&to=                 GET /graph/{investigation_id}/export?format=json|graphml
GET  /scores/{investigation_id} (último)  GET /scores/{investigation_id}/history  GET /scores/{investigation_id}/categories/{name}
GET|POST /reports?investigation_id=  GET /reports/{id}/download   (generación real en Fase 11; aquí 501 si no hay renderer)
GET  /collectors   GET|PATCH /collectors/{name} {enabled, timeout_seconds, rate_limit}   PUT|DELETE /collectors/{name}/api-key
POST /collectors/{name}/run {target_id}   GET /collectors/runs?investigation_id=   GET /audit (admin)
```
```python
def require_role(*roles: Role) -> Callable[..., Awaitable[User]]: ...
class Problem(BaseModel): type: str; title: str; status: int; detail: str | None; instance: str | None
class Page[T](BaseModel): items: list[T]; total: int; limit: int; offset: int
class FindingRead(BaseModel):   # campos de Finding + severity + confidence_factors + is_fact + evidence_id
    ...
```
Permisos: `viewer` lectura; `analyst` crear/escanear/editar sus investigaciones; `admin` todo + collectors + auditoría.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Por recurso (SQLite + `InlineJobQueue` + `InMemoryGraphStore`): CRUD feliz, 404, 422, permisos por rol.
- Auth: login correcto/incorrecto (mensaje genérico), cookie `HttpOnly/Secure/SameSite`, expiración por
  inactividad y absoluta con reloj falso, logout invalida, token Bearer revocado ⇒ 401.
- CSRF: POST sin cabecera ⇒ 403; con cookie+cabecera ⇒ OK; Bearer no requiere CSRF.
- Rate limit: superar `api_rate_limit_per_minute` ⇒ 429 con `Retry-After`; login con su propio límite.
- API keys: nunca aparecen en respuestas, logs (capturar con `structlog.testing`) ni auditoría.
- `DELETE /investigations/{id}` borra findings, evidencia, scores, informes y encola borrado del grafo.
- `/scan` devuelve 202 + job id; `/progress` refleja `collector_runs`.
- OpenAPI: todos los paths de SPECS.md §17 presentes, con tags y esquemas de error.
- Integration: el mismo flujo CRUD contra PostgreSQL real.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run alembic upgrade head && uv run alembic check
uv run pytest tests/unit/api -q
uv run uvicorn app.main:app & sleep 3; curl -s localhost:8000/api/v1/openapi.json | python -m json.tool | grep '"/api/v1/' | wc -l
uv run osint admin create-user --email admin@example.org --role admin   # pide la contraseña sin eco
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Renderizado de informes (Fase 11), UI (Fase 9), comandos CLI de cliente (Fase 10), OIDC/SSO.

## Riesgos y trampas conocidas
- No filtrar existencia de recursos de otros usuarios: 404 (no 403) para investigaciones ajenas.
- `SameSite=Strict` + proxy de Vite funciona porque es mismo origen; en producción, mismo dominio.
- Mensajes de error de login idénticos para usuario inexistente y contraseña errónea (y tiempo constante).
- Validar `limit`, `depth` y filtros en los esquemas (no confiar en el servicio).
- No incluir `Evidence.content` en listados (solo en `GET /evidence/{id}`), por tamaño y privacidad.
- `FastAPI` + `Page[T]` genérico: comprobar que OpenAPI genera nombres de esquema estables.
