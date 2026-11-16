# Fase 2: Backend + modelos + PostgreSQL

## Objetivo
Persistir investigaciones, objetivos, findings, evidencias, fuentes, entidades, relaciones,
scores, informes, ejecuciones de collectors, auditoría y outbox del grafo en PostgreSQL con
SQLAlchemy 2.x async y Alembic. Exponer servicios de investigación (crear, duplicar, abrir,
cerrar, eliminar por completo) y un `FindingPersister` que guarda la salida de los collectors.

## Dependencias (fases previas y contratos que usa)
- Fase 1: `app/domain/*` (Target, Finding, Evidence, Source, enums), `app/core/config.py`
  (`settings.evidence.max_content_bytes`), `app/core/settings.py` (`DATABASE_URL`).
- `app/collectors/resilience.py::CollectorOutcome` (se persiste como `collector_runs`).

## Archivos a crear o modificar (rutas exactas)
- `docker-compose.yml` (raíz): servicios `postgres` (postgres:17-alpine) y `redis` (redis:7-alpine),
  healthchecks, volúmenes nombrados, variables desde `.env` (`POSTGRES_*`). Puertos 5432/6379.
- `backend/alembic.ini`, `backend/alembic/env.py` (async, lee `DATABASE_URL`), `backend/alembic/script.py.mako`,
  `backend/alembic/versions/0001_initial_schema.py`.
- `backend/app/db/base.py` (`Base`, `naming_convention`), `backend/app/db/types.py` (`UTCDateTime`, `JSONType`),
  `backend/app/db/session.py` (engine, `async_sessionmaker`, dependencia FastAPI `get_session`),
  `backend/app/db/uow.py` (`UnitOfWork`).
- `backend/app/models/{investigation,target,source,evidence,finding,entity,relationship,score,report,collector_run,audit,outbox}.py`
  y `backend/app/models/__init__.py` (importa todos para Alembic).
- `backend/app/repositories/{base,investigations,targets,sources,evidence,findings,entities,relationships,scores,collector_runs,audit,outbox,mappers}.py`.
- `backend/app/services/investigations.py`, `backend/app/services/persistence.py`.
- `backend/app/schemas/investigation.py` (`InvestigationCreate`, `InvestigationRead`, `TargetCreate`; DTOs mínimos).
- `backend/app/api/v1/health.py`: añadir `GET /api/v1/health/ready` (comprueba BD; 503 si cae).
- `backend/app/main.py`: `lifespan` que crea y libera el engine.
- Tests: `backend/tests/unit/db/`, `backend/tests/unit/repositories/`, `backend/tests/unit/services/`,
  `backend/tests/integration/test_postgres_migrations.py`; fixtures en `backend/tests/conftest.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-003: SQLAlchemy async + Alembic, tipos portables, una tabla `entities`, solo repositorios hacen SQL.
- ADR-004: `graph_outbox` se escribe en la misma transacción que entidades/relaciones (se usa en Fase 5/6).
- ADR-010: columna `is_synthetic` en `investigations`, `evidence`, `findings`, `sources`.
- ADR-014: tests de repositorio sobre SQLite (aiosqlite); integración con `OSINT_TEST_DATABASE_URL`.
- Enums como `sa.Enum(..., native_enum=False, length=32)` (añadir valores no exige migración de tipo).
- Columnas reservadas para Fase 7 ya en la migración inicial: `findings.confidence_factors` (JSON, null)
  y `findings.severity` (null). Usuarios/sesiones llegan en la Fase 8 (`owner_id` nullable aquí).

## Interfaces y firmas clave (código)
```python
# app/db/types.py
class UTCDateTime(TypeDecorator[datetime]):   # rechaza naive; devuelve siempre tz=UTC (SQLite incluido)
    impl = DateTime(timezone=True); cache_ok = True
JSONType = JSON().with_variant(JSONB(), "postgresql")

# app/db/uow.py
class UnitOfWork:
    investigations: InvestigationRepository; targets: TargetRepository; findings: FindingRepository
    evidence: EvidenceRepository; sources: SourceRepository; entities: EntityRepository
    relationships: RelationshipRepository; scores: ScoreRepository
    collector_runs: CollectorRunRepository; audit: AuditRepository; outbox: OutboxRepository
    async def __aenter__(self) -> "UnitOfWork": ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...

# app/repositories/findings.py
class FindingRepository:
    async def add_many(self, findings: Sequence[Finding]) -> None: ...
    async def list_by_investigation(self, investigation_id: UUID, *, types: set[FindingType] | None = None,
                                    min_confidence: float = 0.0, limit: int = 100, offset: int = 0) -> list[Finding]: ...
    async def get(self, finding_id: UUID) -> Finding | None: ...

# app/services/persistence.py
class FindingPersister:
    def __init__(self, uow_factory: Callable[[], UnitOfWork], evidence_cfg: EvidenceSection) -> None: ...
    async def persist(self, outcome: CollectorOutcome, sources: Sequence[Source]) -> int:
        """Upsert sources, insert evidence (dedupe por id, truncado a max_content_bytes con
        metadata 'truncated': true y sha256 del original), insert findings, insert collector_run."""

# app/services/investigations.py
class InvestigationService:
    async def create(self, name: str, description: str | None, is_synthetic: bool = False) -> InvestigationRead: ...
    async def add_target(self, investigation_id: UUID, target: TargetCreate) -> Target: ...
    async def duplicate(self, investigation_id: UUID, new_name: str) -> InvestigationRead: ...  # copia targets, no findings
    async def close(self, investigation_id: UUID) -> None: ...   # status CLOSED, read-only después
    async def reopen(self, investigation_id: UUID) -> None: ...
    async def delete(self, investigation_id: UUID) -> None: ...  # borra TODO (cascade) + outbox 'delete_investigation'
```
`mappers.py` convierte ORM ⇄ dominio (`finding_to_domain`, `finding_to_row`, …); el resto del
código nunca recibe objetos ORM.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Unit (SQLite en memoria, `Base.metadata.create_all`): round-trip de cada mapper conserva todos los
  campos de `Finding` (incl. `raw_value`, `normalization_steps`, `relation_hint`, tz UTC).
- `FindingPersister`: deduplica evidencia compartida, trunca contenido grande y lo marca, guarda
  `collector_run` con estado/duración/nº findings/error; findings sin evidencia previa fallan.
- `InvestigationService`: crear, duplicar (targets copiados con ids nuevos), cerrar (escrituras
  posteriores lanzan `InvestigationClosedError`), eliminar (0 filas residuales en todas las tablas).
- `GET /api/v1/health/ready` → 200 con SQLite; 503 con engine roto (monkeypatch).
- Integration (`@pytest.mark.integration`, skip sin `OSINT_TEST_DATABASE_URL`): `alembic upgrade head`,
  `downgrade base`, `upgrade head` sobre PostgreSQL real; inserción JSONB y consulta por tipo.

## Criterios de aceptación verificables (comandos concretos)
```bash
docker compose up -d postgres redis              # si hay Docker
cd backend
uv run alembic upgrade head && uv run alembic check   # sin diferencias pendientes
uv run pytest -q                                      # todo verde (integración se salta sin URL)
OSINT_TEST_DATABASE_URL=postgresql+asyncpg://... uv run pytest -m integration -q
uv run ruff check . && uv run black --check . && uv run mypy
uv run uvicorn app.main:app  # y curl localhost:8000/api/v1/health/ready -> 200
```

## Fuera de alcance
Usuarios, sesiones y auth (Fase 8); lógica de ER/correlación (Fase 5); Neo4j (Fase 6); cálculo de
scores (Fase 7); endpoints CRUD públicos (Fase 8). Los modelos `entities/relationships/scores/reports`
solo se crean (tabla + repositorio básico).

## Riesgos y trampas conocidas
- SQLite pierde la zona horaria: usar siempre `UTCDateTime`, nunca `DateTime` a pelo.
- `JSONB` no existe en SQLite: usar `JSONType`; no usar operadores JSONB en repositorios comunes.
- Alembic autogenerate no detecta bien `CheckConstraint`/enums no nativos: revisar la migración a mano.
- `expire_on_commit=False` en el sessionmaker (si no, acceso lazy tras commit falla en async).
- Borrado total: `ON DELETE CASCADE` en todas las FKs hacia `investigations`, más test que lo verifique.
- No guardar `Evidence.content` más allá de `max_content_bytes`; nunca guardar cabeceras de petición.
