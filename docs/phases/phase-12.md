# Fase 12: Testing integral + modo demo offline

## Objetivo
Cerrar la estrategia de tests de SPECS.md §25: escenario end-to-end completo, suites de integración
con PostgreSQL/Neo4j/Redis, cobertura mínima, guardas contra red real y CI. Implementar el modo demo
offline de SPECS.md §26 (ADR-010), que el e2e reutiliza.

## Dependencias (fases previas y contratos que usa)
- Fases 2–11 completas. `CollectorDependencies.synthetic` (Fase 1), `DependencyFactory` (Fase 3),
  `DnsResolver`/`TlsFetcher` (Fase 4a), adaptadores con mock (Fase 4b), `settings.demo`.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/demo/transport.py`: `DemoTransport(httpx.AsyncBaseTransport)` que sirve
  `backend/app/demo/data/http/<host>/<path>.json` (404 si no existe).
- `backend/app/demo/resolver.py`: `DemoResolver` desde `backend/app/demo/data/dns/zones.yaml`; `DemoTlsFetcher`.
- `backend/app/demo/data/`: dataset sintético (dominios `*.example`, `example.com/org/net`, IPs
  RFC 5737/3849, teléfonos `+1 555 01xx`, personas ficticias) + `README.md` con su origen ("generado a mano").
- `backend/app/demo/loader.py`: `DemoLoader.load() -> list[UUID]` (crea 2–3 investigaciones y las ejecuta).
- `backend/app/collectors/deps.py`: en demo ⇒ `synthetic=True`, `DemoTransport`, `DemoResolver`, claves ficticias.
- `backend/app/api/v1/demo.py`: `POST /api/v1/demo/load` (404 si no está en modo demo). `backend/app/cli/commands/demo.py`.
- `backend/tests/e2e/test_pipeline.py`, `backend/tests/e2e/conftest.py`.
- `backend/tests/conftest.py`: guarda de red autouse (unitarios) y fixtures `integration` que hacen skip sin URL.
- `backend/tests/integration/{test_postgres_repositories.py,test_neo4j_sync.py,test_pipeline_real_stores.py}`.
- `.github/workflows/ci.yml`: jobs backend (ruff, black, mypy, pytest + cobertura), frontend (lint, typecheck,
  test, build) e integración con servicios `postgres`, `neo4j`, `redis`.
- `backend/pyproject.toml`: `addopts` con `--cov=app --cov-fail-under=80` solo en CI (vía `PYTEST_ADDOPTS`).

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-010: los collectors reales corren contra transportes sintéticos; todo queda `is_synthetic=True`.
- ADR-014: unitarios sin red; integración con `OSINT_TEST_*`; e2e en modo inline + demo + SQLite + `InMemoryGraphStore`
  (y variante con stores reales marcada `integration`).
- La guarda de red: monkeypatch de `socket.socket.connect` que solo permite `127.0.0.1/::1` (los event
  loops de Windows usan socketpair local); cualquier otra dirección ⇒ `RuntimeError("network access in tests")`.
- Ningún dato del dataset puede ser real: test que valida dominios/IP/teléfonos contra rangos reservados.

## Interfaces y firmas clave (código)
```python
class DemoTransport(httpx.AsyncBaseTransport):
    def __init__(self, data_dir: Path) -> None: ...
    async def handle_async_request(self, request: httpx.Request) -> httpx.Response: ...

class DemoResolver:          # implementa DnsResolver
    def __init__(self, zones_file: Path) -> None: ...
    async def resolve(self, name: str, rdtype: str) -> DnsAnswer: ...

class DemoLoader:
    def __init__(self, investigations: InvestigationService, orchestrator: InvestigationOrchestrator,
                 reports: ReportService) -> None: ...
    async def load(self) -> list[UUID]: ...

RESERVED_DOMAINS = ("example", "example.com", "example.org", "example.net", "test", "invalid")
RESERVED_NETWORKS = ("192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")
```
Escenario e2e (SPECS.md §25): create investigation → add target (`acme.example` + persona ficticia con
semillas) → run collectors → findings → correlate → score → graph sync → generate report (HTML+JSON).

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- E2E (`@pytest.mark.e2e`): estado `COMPLETED` o `COMPLETED_WITH_WARNINGS` (un collector configurado para
  fallar en el dataset); findings de ≥8 collectors; entidades y relaciones > 0; al menos una `POSSIBLY_SAME_AS`
  CORRELATED; score 0–100 con contribuciones; informe HTML con banner "DEMO / SYNTHETIC DATA".
- Trazabilidad e2e: cada finding del informe tiene evidencia o `derived_from` resoluble hasta evidencia.
- Ningún finding INFERRED/CORRELATED aparece en la sección de hechos observados.
- Dataset: todos los valores pertenecen a rangos reservados; la guarda de red bloquea `example.com:443` real.
- Integración (con servicios): repositorios en PostgreSQL, sync Neo4j, rate limiter Redis, pipeline real.
- Frontend: tests de 9a/9b + un test de humo que renderiza la app con MSW y navega por todas las pestañas.
- Cobertura: backend ≥ 80 % líneas (`--cov-fail-under=80`); informe en CI.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run pytest -q                                   # unit + e2e (sin red)
uv run pytest -m e2e -q
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
OSINT_TEST_DATABASE_URL=... OSINT_TEST_NEO4J_URI=... OSINT_TEST_REDIS_URL=... uv run pytest -m integration -q
OSINT_DEMO_MODE=true uv run osint --local demo load --json
cd ../frontend && npm test -- --run
```

## Fuera de alcance
Pruebas de carga, fuzzing de la API, tests contra APIs externas reales (prohibidos en la suite).

## Riesgos y trampas conocidas
- La guarda de red no debe romper `asyncio` en Windows (socketpair a 127.0.0.1): permitir loopback.
- Tests e2e lentos: reloj y `sleep` inyectados, backoff con `jitter=0` y `backoff_base_seconds` mínimo en config de test.
- El dataset demo debe mantenerse coherente con los parsers: si cambia un collector, actualizar sus fixtures.
- Cobertura alta no sustituye a asserts de contrato: priorizar tests de provenance y explicabilidad.
