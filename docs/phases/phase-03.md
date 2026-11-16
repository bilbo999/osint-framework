# Fase 3: Sistema de collectors / plugins (ejecución, resiliencia, workers)

## Objetivo
Convertir el contrato de la Fase 1 en un motor de ejecución real: resiliencia completa (timeout,
retry con backoff, rate limit, circuit breaker), orquestación paralela de collectors por
investigación con pivots, cola arq, logging estructurado y métricas. Un fallo de un collector
nunca detiene la investigación (estado final `COMPLETED_WITH_WARNINGS`).

## Dependencias (fases previas y contratos que usa)
- Fase 1: `Collector`, `CollectorDependencies`, `CollectorRegistry`, `ResiliencePolicy`,
  `compute_backoff`, protocolos `RateLimiter`/`CircuitBreaker`/`ResilientExecutor`, `CollectorOutcome`,
  errores de `app/collectors/errors.py`, `settings.execution`, `settings.http`, `settings.logging`.
- Fase 2: `FindingPersister`, `CollectorRunRepository`, `TargetRepository`, `UnitOfWork`.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/collectors/resilience.py`: añadir `InMemoryRateLimiter`, `RedisRateLimiter`,
  `InMemoryCircuitBreaker`, `CircuitBreakerRegistry`, `DefaultResilientExecutor` (no cambiar las firmas existentes).
- `backend/app/collectors/http.py`: `build_http_client()` y `raise_for_status_mapped()`.
- `backend/app/collectors/deps.py`: `DefaultDependencyFactory` (cliente HTTP compartido + API key desde entorno).
- `backend/app/services/orchestrator.py`: `InvestigationOrchestrator`.
- `backend/app/services/queue.py`: `JobQueue` (protocolo), `ArqJobQueue`, `InlineJobQueue`.
- `backend/app/workers/settings.py` (`WorkerSettings` de arq), `backend/app/workers/jobs.py` (`run_investigation`).
- `backend/app/core/logging.py`: `configure_logging()`, procesador `redact_secrets`.
- `backend/app/core/metrics.py`: contadores/histogramas Prometheus.
- Tests: `backend/tests/fixtures/fakes.py` (ampliar), `backend/tests/unit/collectors/test_executor.py`,
  `test_rate_limiter.py`, `test_circuit_breaker.py`, `test_http.py`, `backend/tests/unit/services/test_orchestrator.py`,
  `backend/tests/unit/core/test_logging.py`, `backend/tests/integration/test_redis_rate_limiter.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-002: arq + `asyncio.TaskGroup` + semáforo global + token bucket por collector (Redis Lua).
- ADR-012: el executor llama a `collector.validate_output()`; contrato roto ⇒ `ERROR`, sin reintento.
- ADR-013: evento `collector_run` con los campos de SPECS.md §23; nunca loguear cuerpos ni cabeceras.
- Collectors con `requires_api_key` y sin clave ⇒ `SKIPPED` con `error="missing_api_key"` (sin llamar a `collect`).
- Circuit breaker en memoria por proceso worker (aceptable: protege la fuente, no requiere consenso).
- Estado final: todo `SUCCESS` ⇒ `COMPLETED`; algún no-`SUCCESS` y ≥1 `SUCCESS` ⇒ `COMPLETED_WITH_WARNINGS`;
  ningún `SUCCESS` ⇒ `FAILED`. Pivots: findings de `execution.pivot_finding_types` crean `Target` hijo
  (`parent_target_id`, `pivot_depth+1`) mientras `pivot_depth < execution.max_pivot_depth`, sin duplicar
  `(type, normalized_value)` ya presentes en la investigación.

## Interfaces y firmas clave (código)
```python
class InMemoryRateLimiter:                       # implementa RateLimiter
    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep) -> None: ...
    async def acquire(self, key: str, limit: RateLimit) -> None: ...

class RedisRateLimiter:                          # mismo protocolo; script Lua atómico
    def __init__(self, redis: Redis, prefix: str = "osint:rl:") -> None: ...

class InMemoryCircuitBreaker:                    # implementa CircuitBreaker
    def __init__(self, policy: CircuitBreakerConfig, clock: Callable[[], float] = time.monotonic) -> None: ...

class DefaultResilientExecutor:                  # implementa ResilientExecutor
    def __init__(self, rate_limiter: RateLimiter, breakers: CircuitBreakerRegistry,
                 sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
                 clock: Callable[[], float] = time.monotonic) -> None: ...
    async def run(self, collector: Collector, target: Target) -> CollectorOutcome: ...

def raise_for_status_mapped(response: httpx.Response) -> None:
    """429 -> RateLimitedError(retry_after=Retry-After); 5xx/RequestError -> TransientCollectorError;
    otros 4xx -> PermanentCollectorError. 404 NO es error: lo decide cada collector."""

class InvestigationOrchestrator:
    def __init__(self, registry: CollectorRegistry, executor: ResilientExecutor,
                 persister: FindingPersister, uow_factory: Callable[[], UnitOfWork],
                 deps_factory: DependencyFactory, config: AppConfig) -> None: ...
    async def run(self, investigation_id: UUID, only: Sequence[str] | None = None) -> InvestigationStatus: ...
    async def progress(self, investigation_id: UUID) -> list[CollectorProgress]: ...

class JobQueue(Protocol):
    async def enqueue_investigation(self, investigation_id: UUID, only: Sequence[str] | None = None) -> str: ...
```
`CollectorProgress(collector: str, target_id: UUID, status: CollectorRunStatus, findings: int,
duration_seconds: float | None)` alimenta la barra de progreso de SPECS.md §22.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Executor con reloj/sleep falsos: éxito; timeout ⇒ `TIMEOUT` tras `max_attempts`; transitorio 2 veces y
  luego éxito ⇒ `SUCCESS`, `attempts=3`, sleeps = `compute_backoff`; `RateLimitedError(retry_after=7)` ⇒
  espera 7; permanente ⇒ 1 intento; contrato roto ⇒ `ERROR`; breaker abierto ⇒ `CIRCUIT_OPEN` sin llamar.
- Excepción inesperada (`RuntimeError`) en un collector ⇒ `ERROR`, el executor no propaga.
- Token bucket: N+1 llamadas en ventana ⇒ la última espera `1/refill`; claves independientes no se bloquean.
- Breaker: CLOSED→OPEN tras `failure_threshold`, OPEN→HALF_OPEN tras `recovery_timeout`, HALF_OPEN→CLOSED/OPEN.
- Orchestrator (SQLite + fakes): 4 collectors (uno con timeout) ⇒ `COMPLETED_WITH_WARNINGS` y findings
  de los otros tres persistidos; ejecución paralela (duración total < suma); pivot crea hijos hasta
  `max_pivot_depth`; collector sin API key ⇒ `SKIPPED`.
- Logging: `redact_secrets` sustituye valores de claves en `redact_keys` (también anidados).
- HTTP: `respx` para 200/404/429/503 y verificación de User-Agent genérico de `settings.http.user_agent`.
- Integration (Redis real, `OSINT_TEST_REDIS_URL`): dos limiters comparten el mismo bucket.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run pytest tests/unit/collectors tests/unit/services -q
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
uv run python -c "from app.workers.settings import WorkerSettings; print(WorkerSettings.functions)"
docker compose up -d redis && uv run arq app.workers.settings.WorkerSettings  # arranca y espera jobs (Ctrl+C)
```

## Fuera de alcance
Collectors reales (Fase 4a/4b); correlación/scoring tras la ejecución (Fases 5 y 7 se enganchan al
final de `run`); endpoint REST de scan/progreso (Fase 8); UI de progreso (Fase 9a).

## Riesgos y trampas conocidas
- `asyncio.timeout` cancela la tarea: los collectors deben ser cancel-safe (sin estado global).
- No reintentar `CancelledError`; propagar cancelación de la investigación completa.
- `TaskGroup` cancela hermanos si una tarea lanza: el wrapper de cada tarea NUNCA debe lanzar.
- Rate limiter + retry: el `acquire` va dentro del bucle de intentos (cada intento consume token).
- Cerrar el `httpx.AsyncClient` compartido al terminar el job (fuga de conexiones).
- En Windows, arq/uvloop: usar el event loop por defecto; no depender de uvloop.
