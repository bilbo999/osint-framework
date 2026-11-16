# Fase 6: Neo4j + grafo

## Objetivo
Proyectar entidades y relaciones de PostgreSQL en Neo4j mediante el outbox y ofrecer consultas de
grafo: vecinos, shortest path, expansión de entidades, subgrafo filtrado por tipo y confianza, y
exportación en el formato que consumirá Cytoscape (SPECS.md §9).

## Dependencias (fases previas y contratos que usa)
- Fase 2: tabla `graph_outbox`, `OutboxRepository`, `docker-compose.yml`.
- Fase 3: arq (`WorkerSettings`) para el job `sync_graph`; `JobQueue`.
- Fase 5: `Entity`, `Relationship`, `CorrelationService` (escribe el outbox), `settings.graph`.

## Archivos a crear o modificar (rutas exactas)
- `docker-compose.yml`: servicio `neo4j` (neo4j:5-community), puertos 7474/7687, `NEO4J_AUTH` desde `.env`,
  healthcheck con `cypher-shell`, volumen `neo4j_data`.
- `backend/app/graph/driver.py`: creación/cierre de `AsyncDriver` (desde `EnvSettings`).
- `backend/app/graph/store.py`: protocolo `GraphStore`, `Neo4jGraphStore`, `InMemoryGraphStore` (tests).
- `backend/app/graph/schema.py`: constraints/índices idempotentes (`CREATE CONSTRAINT IF NOT EXISTS`).
- `backend/app/graph/cypher.py`: construcción segura de consultas (labels/tipos desde enums).
- `backend/app/graph/sync.py`: `GraphSyncService` (drena outbox por lotes de `outbox_batch_size`).
- `backend/app/graph/queries.py`: `GraphQueryService`.
- `backend/app/graph/export.py`: `to_cytoscape(subgraph) -> CytoscapeGraph`, `to_graphml(subgraph) -> str`.
- `backend/app/workers/jobs.py`: job `sync_graph`; `backend/app/workers/settings.py`: registrarlo.
- `backend/app/api/v1/health.py`: `ready` incluye Neo4j (degradado ⇒ 503 con detalle por dependencia).
- Tests: `backend/tests/unit/graph/test_cypher.py`, `test_sync.py`, `test_queries_inmemory.py`, `test_export.py`;
  `backend/tests/integration/test_neo4j_store.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-004: Neo4j es proyección; PostgreSQL manda. `rebuild(investigation_id | None)` reconstruye.
- Nodo: label = `EntityType` en PascalCase (`Domain`, `IpAddress`, …) + label común `:Entity`;
  propiedades `id`, `investigation_id`, `type`, `value`, `is_synthetic`, `sources`.
- Relación: tipo = `RelationType` (ya en mayúsculas); propiedades `id`, `confidence`, `provenance_kind`,
  `evidence_finding_ids`, `investigation_id`.
- Toda consulta filtra por `investigation_id` (aislamiento entre investigaciones).
- Labels y tipos de relación **no** se pueden parametrizar en Cypher: solo valores de los enums (whitelist).
- Sin APOC ni GDS (no disponibles en community por defecto).

## Interfaces y firmas clave (código)
```python
class GraphNode(BaseModel):  id: UUID; type: EntityType; value: str; properties: dict[str, JsonValue]
class GraphEdge(BaseModel):  id: UUID; type: RelationType; source: UUID; target: UUID
                             confidence: float; provenance_kind: ProvenanceKind
class Subgraph(BaseModel):   nodes: list[GraphNode]; edges: list[GraphEdge]; truncated: bool

class GraphStore(Protocol):
    async def ensure_schema(self) -> None: ...
    async def upsert_entities(self, entities: Sequence[Entity]) -> None: ...
    async def upsert_relationships(self, relationships: Sequence[Relationship]) -> None: ...
    async def delete_investigation(self, investigation_id: UUID) -> None: ...
    async def neighbors(self, investigation_id: UUID, entity_id: UUID, depth: int,
                        types: set[EntityType] | None, min_confidence: float, limit: int) -> Subgraph: ...
    async def shortest_path(self, investigation_id: UUID, a: UUID, b: UUID, max_depth: int) -> Subgraph | None: ...
    async def subgraph(self, investigation_id: UUID, types: set[EntityType] | None,
                       min_confidence: float, limit: int) -> Subgraph: ...

class GraphSyncService:
    async def drain(self, max_batches: int | None = None) -> int: ...      # nº de eventos aplicados
    async def rebuild(self, investigation_id: UUID | None = None) -> int: ...

class GraphQueryService:   # valida depth ≤ settings.graph.max_expand_depth y limit ≤ max_nodes_returned
    async def expand(self, investigation_id: UUID, entity_id: UUID, depth: int = 1, **filters) -> Subgraph: ...

class CytoscapeGraph(BaseModel):
    elements: list[dict[str, JsonValue]]   # [{"data": {"id", "label", "type", "confidence", ...}}]
```
Eventos de outbox: `upsert_entity`, `upsert_relationship`, `delete_investigation` con `payload` = ids;
el servicio relee las filas de PostgreSQL (no confía en payloads obsoletos) y marca `processed_at`.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- `cypher.py`: un label fuera del enum lanza `ValueError`; las consultas generadas usan parámetros para valores.
- `GraphSyncService` con `InMemoryGraphStore` + SQLite: drena en lotes, es idempotente (reprocesar no duplica),
  un evento fallido queda pendiente con `attempts+1` y no bloquea el resto.
- `rebuild` produce el mismo grafo que la sincronización incremental.
- `InMemoryGraphStore` implementa vecinos, shortest path y filtros con la misma semántica que Neo4j
  (los tests de queries se ejecutan contra ambos stores: parametrizar fixture).
- Filtros: `min_confidence=0.7` excluye aristas con 0.6 y nodos que quedan aislados; filtro por tipo.
- Límites: `depth > max_expand_depth` ⇒ error de validación; `limit` alcanzado ⇒ `truncated=True`.
- Export: `to_cytoscape` estable (ordenado) y con `provenance_kind` por arista; GraphML válido (parse con `xml.etree`).
- Integration (`OSINT_TEST_NEO4J_URI`): constraints creados, upsert idempotente, `delete_investigation` limpia todo.

## Criterios de aceptación verificables (comandos concretos)
```bash
docker compose up -d neo4j
cd backend
uv run pytest tests/unit/graph -q
OSINT_TEST_NEO4J_URI=bolt://localhost:7687 uv run pytest -m integration tests/integration/test_neo4j_store.py -q
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Endpoints REST del grafo (Fase 8), visualización (Fase 9b), algoritmos de centralidad/comunidades.

## Riesgos y trampas conocidas
- `shortestPath` sin límite de longitud puede ser costoso: siempre `[*..max_depth]`.
- Sesiones async del driver: una por operación; cerrar el driver en `lifespan` y en el worker.
- Escritura en lotes con `UNWIND $rows AS row MERGE ...` (no un query por nodo).
- No borrar nodos compartidos entre investigaciones: cada nodo pertenece a una única investigación (id propio).
- Si Neo4j cae, la investigación sigue: el outbox acumula y se drena al volver (no fallar el pipeline).
