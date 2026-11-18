# Arquitectura

Documento vivo. Las decisiones se registran como ADR: un ADR aceptado solo se cambia
añadiendo otro que lo sustituya ("Supersedes ADR-00X"). Especificación: [SPECS.md](SPECS.md).
Plan por fases: [phases/](phases/). Reglas de trabajo: [../CLAUDE.md](../CLAUDE.md).

## 1. Visión general

```text
 React + Mantine + Cytoscape (frontend/)      CLI Typer (HTTP o ASGI in-process)
                 └──────────────┬──────────────────────┘
                                ▼
                  FastAPI /api/v1 (app/api) ──► services (app/services)
                                                   │ encola
                                                   ▼
          arq + Redis ──► worker: Orchestrator ──► ResilientExecutor ──► Collector.collect()
                                │ (asyncio, token bucket, circuit breaker)     │ list[Finding] (+Evidence)
                                ▼                                              │
                     FindingPersister ◄────────────────────────────────────────┘
                                │ PostgreSQL = fuente de verdad
                                ├─► analyzers: normalizers, EntityResolver, CorrelationEngine
                                ├─► scoring: ConfidenceService, ExposureService
                                ├─► graph_outbox ──► GraphSyncService ──► Neo4j (proyección)
                                └─► reports: HTML / JSON / CSV / PDF
```

Dependencias permitidas (solo hacia la derecha):
`api → services → (collectors | analyzers | scoring | graph | reports) → repositories → models → domain`.
`app/domain` = contratos Pydantic puros sin I/O; `app/models` = ORM; `app/schemas` = DTOs de API.
Cadena de datos (SPECS.md §32): Evidence (raw) → Finding (normalized_value + normalization_steps)
→ Entity → Relationship → INFERRED/CORRELATED → Exposure; cada paso guarda el id del anterior.

## 2. ADRs

**ADR-001 — Estructura del repositorio.** Monorepo: `backend/` (paquete `app`, `pyproject.toml`
y `uv.lock` propios), `frontend/`, `config/` (YAML compartido), `collectors/` (plugins externos
por ruta), `docs/`, `scripts/`, `docker/`. Contratos de dominio en `app/domain`, separados del ORM
(`app/models`) y de los DTOs (`app/schemas`) para que esquema de BD y API evolucionen por separado.
*Descartado:* `pyproject.toml` en la raíz (mezcla tooling Python/Node y complica la imagen Docker).

**ADR-002 — Ejecución asíncrona.** **arq** (cola nativa asyncio sobre Redis) encola
`run_investigation`; dentro del job un `asyncio.TaskGroup` lanza los collectors en paralelo con
semáforo global (`execution.max_concurrent_collectors`) y **token bucket por collector en Redis**
(compartido entre workers). `execution.backend: inline` ejecuta lo mismo en proceso (tests, CLI).
*Descartado:* Celery (síncrono, collectors async incómodos); `BackgroundTasks` (se pierde al reiniciar).

**ADR-003 — Persistencia.** SQLAlchemy 2.x `AsyncSession` + asyncpg, modelos `Mapped[...]` en
`app/models/<agregado>.py` con `naming_convention`; solo `app/repositories` emite SQL, servicios vía
Unit of Work. Alembic async con autogenerate (nunca editar una migración aplicada). Tipos portables
(`Uuid`, `JSON().with_variant(JSONB)`) ⇒ tests de repositorio en SQLite. Entidades en una tabla `entities`.
*Descartado:* una tabla por tipo de entidad (11 tablas casi iguales y joins polimórficos).

**ADR-004 — PostgreSQL vs Neo4j.** PostgreSQL es la fuente de verdad; Neo4j una proyección
reconstruible. Cada alta/cambio de entidad o relación escribe en la misma transacción una fila en
`graph_outbox`; `GraphSyncService` (job `sync_graph`) la aplica con `MERGE` idempotente por `id`.
`osint graph rebuild` regenera Neo4j desde cero. Solo `app/graph` importa el driver de Neo4j.
*Descartado:* doble escritura desde servicios (inconsistencia si falla una de las dos bases).

**ADR-005 — Autenticación y secretos.** Contraseñas argon2id; sesión opaca de servidor (token de
256 bits en cookie `HttpOnly; Secure; SameSite=Strict`, solo su SHA-256 en `user_sessions`) + CSRF
por cabecera; tokens personales `osk_…` hasheados para CLI. Roles `admin|analyst|viewer`. API keys:
entorno primero; las de la UI cifradas con Fernet (`OSINT_ENCRYPTION_KEY`), nunca devueltas ni logueadas.
*Descartado:* JWT (revocación difícil); OIDC (excesivo para despliegue local, ampliable después).

**ADR-006 — Entity resolution.** Merge exacto por `(type, normalized_value)` solo para
`auto_merge_entity_types`; para el resto, blocking + score ponderado (Jaro-Winkler con rapidfuzz,
contexto, diversidad de fuentes, referencias cruzadas). ≥ `link_threshold` crea `POSSIBLY_SAME_AS`
(CORRELATED, con evidencias); persona/organización/username nunca se fusionan. Umbrales y pesos en
`settings.yaml → entity_resolution`. *Descartado:* clustering transitivo (A≈B≈C ⇒ identidades falsas).

**ADR-007 — Confidence.** `confidence = min(provenance_caps[kind], Σ wᵢ·fᵢ)` con cinco factores
en [0,1]: fiabilidad de fuente, calidad de evidencia, coincidencia de entidad, corroboración y
frescura. Pesos, topes y tablas en `scoring.yaml → confidence`; el desglose se persiste con el valor.
El valor del collector es provisional (`provisional_confidence`) y siempre se recalcula.
*Descartado:* confianza fijada por cada collector (no comparable entre fuentes ni configurable).

**ADR-008 — Exposure Score.** 7 categorías con `max_points` que suman 100 (validado al cargar).
Cada regla aporta `points × confidence × provenance_multiplier` en sus `max_occurrences` mejores
elementos; la categoría satura en `max_points`. Se guarda `Score` (+ `scoring_hash`) y una fila de
`score_contributions` por aportación ⇒ cada componente es clicable hasta sus findings.
*Descartado:* modelo ML u opaco (no explicable) y suma sin saturación (una categoría lo domina todo).

**ADR-009 — UI, grafo y PDF.** Mantine v8 (accesible, completo, sin Tailwind) + TanStack Query
(polling de progreso) + React Router + tipos generados con openapi-typescript. Grafo con
Cytoscape.js (`react-cytoscapejs`, layout fcose). PDF con WeasyPrint desde la misma plantilla
Jinja2 del HTML (extra `pdf`, instalado en Docker). *Descartado:* shadcn/ui (Tailwind + código
copiado); Sigma.js (menos interacción); ReportLab (maquetación duplicada); SSE (polling basta).

**ADR-010 — Demo offline.** Con `OSINT_DEMO_MODE=true` los collectors **reales** se ejecutan contra
transportes sintéticos inyectados por `deps` (`DemoTransport` httpx, `DemoResolver` DNS, fetcher TLS)
que sirven `backend/app/demo/data/`, con `deps.synthetic=True` y API keys ficticias ⇒ todo sale
`is_synthetic=True`. `osint demo load` crea investigaciones de ejemplo. UI, API e informes muestran
"DEMO / SYNTHETIC DATA" (`demo.banner`). *Descartado:* collectors "replay" falsos (no prueban el
código real); grabar respuestas reales (datos personales reales en el repositorio).

**ADR-011 — CLI sobre la API.** La CLI es un cliente httpx de la API REST: `--api-url` contra un
servidor o `--local` con `httpx.ASGITransport(create_app())` en proceso. Siempre pasa por routers,
auth, validación y auditoría, sin duplicar lógica (SPECS.md §18).
*Descartado:* CLI llamando a servicios directamente (se salta auth, validación y auditoría).

**ADR-012 — Contrato de collectors y provenance.** `Collector` declara metadatos `ClassVar`
validados por `metadata()`; `collect(target) -> list[Finding]` y cada Finding transporta su
`Evidence` en el campo transitorio `evidence`. El modelo impone las reglas de provenance (§A.1) y
`validate_output()` impide INFERRED/CORRELATED o tipos/fuentes no declarados. Descubrimiento por
paquete, módulo, ruta y entry point. *Descartado:* `collect()` devolviendo otro tipo (rompe SPECS.md §4).

**ADR-013 — Logging y observabilidad.** structlog JSON con contextvars (`investigation_id`,
`collector`, `target`) y redacción por `logging.redact_keys`. Cada ejecución emite `collector_run`
con los campos de SPECS.md §23 y se persiste en `collector_runs`. Métricas Prometheus en `/metrics`.
*Descartado:* loguear cuerpos HTTP (riesgo de filtrar datos personales y secretos).

**ADR-014 — Tests.** Unitarios sin red ni BD real (respx, resolvers DNS falsos, `deps.clock`);
repositorios sobre SQLite; integración (`-m integration`) contra servicios reales indicados por
`OSINT_TEST_*`, saltados si faltan; un e2e del pipeline completo en modo inline + demo. Cobertura
backend ≥ 80 % desde la Fase 12. *Descartado:* testcontainers obligatorio (exige Docker siempre).

**ADR-015 — Detalles de persistencia de la Fase 2.** Desviaciones/precisiones sobre phase-02.md:
(1) `app/domain/records.py` añade los registros persistidos fuera del contrato de collectors
(`Investigation`, `CollectorRun`, `Entity`, `Relationship`, `Score`, `Report`, `AuditEvent`,
`OutboxEvent`) para que los repositorios nunca devuelvan objetos ORM; también `repositories/reports.py`
y `services/errors.py`. (2) `evidence` tiene columna `metadata` (JSON): al truncar a
`max_content_bytes` se guarda `{"truncated": true, "original_size_bytes", "original_sha256"}` y
`evidence.sha256` sigue siendo el del contenido original; `evidence_to_domain` reconstruye esas filas
con `model_construct` (el validador de hash no aplica a un prefijo). (3) Borrado total: todas las FKs a
`investigations` son `ON DELETE CASCADE`; `audit_log` también cae en cascada y el evento
`investigation.deleted` se guarda con `investigation_id=NULL`; `graph_outbox.investigation_id` **no** tiene
FK para que `delete_investigation` sobreviva hasta que Neo4j se limpie. (4) `sources` es un catálogo global
(PK = `name`) con FK desde `evidence.source` y `findings.source`; `persist()` falla (`MissingSourceError`)
si un finding referencia una fuente ni aportada ni existente, y (`MissingEvidenceError`) si referencia
evidencia ni adjunta ni almacenada; todo ocurre en una sola transacción. (5) `naming_convention["uq"]`
incluye `constraint_name`. (6) `reopen` devuelve a `COMPLETED` si hubo `collector_runs`, si no a `DRAFT`.
(7) SQLite (tests) activa `PRAGMA foreign_keys=ON` en `create_engine` para que los cascades se prueben.
(8) La migración `0001` parte de autogenerate revisado a mano; `alembic check` limpio sobre SQLite.

## Anexo A — Detalles de referencia

### A.1 Reglas de provenance (impuestas por `app/domain/finding.py`)
| Kind | Quién lo emite | Requisito | Tope de confidence (`scoring.yaml`) |
|---|---|---|---|
| OBSERVED | collectors | `evidence_id`, sin `derived_from` | 1.00 |
| DERIVED | collectors / normalizers | `evidence_id` o `derived_from` | 0.95 |
| CORRELATED | CorrelationEngine | `derived_from` no vacío | 0.80 |
| INFERRED | analyzers | `derived_from` no vacío | 0.60 |

UI e informes muestran siempre el kind; INFERRED/CORRELATED se rotulan "inferencia", nunca "hecho".

### A.2 Confidence (ADR-007)
- `source_reliability`: `confidence.source_reliability[Finding.source]` o `default`.
- `evidence_quality`: `confidence.evidence_quality[Evidence.kind]`, `none` si no hay evidencia.
- `entity_match`: 1.0 para OBSERVED/DERIVED; score de ER para CORRELATED/INFERRED.
- `corroboration`: `min(1, fuentes_independientes / corroboration.saturation_sources)`.
- `freshness`: `0.5 ** (edad_días / half_life_days[type] | default_half_life_days)`.
Se guarda `confidence_factors` (JSON) junto al finding para el tooltip "por qué esta confianza".

### A.3 Exposure Score (ADR-008)
Por categoría y regla: filtrar findings (`finding_types` + `metadata_equals`, confidence ≥
`min_confidence`) o relaciones (`relationship_types`); ordenar por aportación, tomar
`max_occurrences`; `categoría = min(max_points, Σ)`; `total = Σ categorías`. Cada aportación →
`score_contributions(score_id, category, rule_id, finding_id | relationship_id, points, explanation)`.

### A.4 Entity resolution (ADR-006)
Blocking: email → local-part; username → minúsculas sin `._-`; persona → inicial + apellido.
`score = Σ feature_weights[f] × f`; ≥ `link_threshold` enlaza, [`review_threshold`, `link_threshold`)
queda como candidato oculto, por debajo se descarta. Máximo `max_candidates_per_entity` por entidad.

### A.5 Mapeo FindingType → EntityType (Fases 5/6)
domain/mx_record/ns_record/reverse_dns → `domain` (o `subdomain` si no es dominio registrable);
subdomain → `subdomain`; ip_address → `ip_address`; email → `email`; username/account_presence →
`username`; phone → `phone`; url → `url`; certificate → `certificate`; autonomous_system →
`autonomous_system`; person_name → `person`; organization → `organization`. El resto (spf_policy,
dmarc_policy, txt_record, geolocation, technology, breach_exposure, *_registration, *_metadata,
email_validation, gravatar_profile, tld) son **atributos** de la entidad sujeto, no nodos.

## 3. Riesgos conocidos
- Docker no está disponible en todas las máquinas de desarrollo ⇒ los tests de integración se saltan sin él.
- WeasyPrint necesita Pango (suele faltar en Windows) ⇒ el test de PDF se salta si no se puede importar.
- Términos de servicio de crt.sh, GitHub, GitLab, Gravatar o HIBP pueden cambiar: límites conservadores
  en `collectors.yaml` y `terms_url` documentado en cada `Source`.
- Falsos positivos en ER ⇒ nunca fusionar personas/usernames; tope de confianza para CORRELATED.
- Toolchain muy reciente (TypeScript 7, Vite 8, SQLAlchemy 2.1, pytest-asyncio 1.x): si un plugin
  no es compatible, fijar versión y anotarlo aquí.
