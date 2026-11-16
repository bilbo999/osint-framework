# Fase 5: Entity resolution + motor de correlación

## Objetivo
Transformar findings en entidades y relaciones trazables: fusionar duplicados exactos, materializar
relaciones afirmadas por las fuentes (`relation_hint`), proponer relaciones potenciales
(`POSSIBLY_SAME_AS`, CORRELATED) sin convertirlas en hechos, detectar evidencias corroborantes y
conflictos entre fuentes (SPECS.md §8, §10).

## Dependencias (fases previas y contratos que usa)
- Fase 1: `Finding` (`normalized_value`, `relation_hint`, `provenance_kind`, `derived_from`),
  `EntityType`, `RelationType`, `settings.entity_resolution`.
- Fase 2: tablas/repositorios `entities`, `relationships`, `graph_outbox`, `UnitOfWork`.
- Fase 3: el orchestrator llama a `CorrelationService.run()` al terminar los collectors.
- Fase 4a/4b: normalizadores (las claves de blocking se construyen sobre valores normalizados).

## Archivos a crear o modificar (rutas exactas)
- `backend/app/domain/entity.py`: `Entity`, `Relationship`, `RelationshipEvidence`, `Conflict`, `MatchScore`.
- `backend/app/analyzers/mapping.py`: `finding_entity_type(finding) -> EntityType | None` (docs/architecture.md §A.5).
- `backend/app/analyzers/blocking.py`, `backend/app/analyzers/features.py`,
  `backend/app/analyzers/entity_resolution.py` (`EntityResolver`), `backend/app/analyzers/correlation.py` (`CorrelationEngine`).
- `backend/app/services/correlation.py`: `CorrelationService` (carga, ejecuta, persiste + outbox).
- `backend/app/models/conflict.py` + migración `backend/alembic/versions/0002_conflicts.py`.
- `backend/app/services/orchestrator.py`: invocar la correlación tras persistir outcomes.
- Tests: `backend/tests/unit/analyzers/test_mapping.py`, `test_blocking.py`, `test_features.py`,
  `test_entity_resolution.py`, `test_correlation.py`; `backend/tests/unit/services/test_correlation_service.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-006 y §A.4: merge exacto solo en `auto_merge_entity_types`; `never_auto_merge_entity_types` solo se enlazan.
- §A.5: mapeo FindingType → EntityType; los demás tipos son atributos (`Entity.attributes[finding_type]`
  guarda lista de `finding_id`, nunca el valor suelto sin referencia).
- `relation_hint` ⇒ relación con `provenance_kind=OBSERVED` y evidencia = ese finding.
- Toda relación CORRELATED/INFERRED guarda ≥1 `RelationshipEvidence(finding_id, role, weight)` y el
  `MatchScore` completo (features + pesos) en `metadata` para poder explicarla.
- Corroboración: mismo `(entity, atributo, valor)` desde ≥2 **fuentes distintas** ⇒ `corroborated_by`.
- Conflicto: atributo funcional (registrar, país, ASN, `not_after` de un mismo serial) con valores
  distintos entre fuentes ⇒ fila `conflicts`; ninguno se descarta, ambos quedan visibles.
- Idempotencia: ejecutar dos veces sobre los mismos findings no crea duplicados (claves naturales).

## Interfaces y firmas clave (código)
```python
class Entity(BaseModel):
    id: UUID; investigation_id: UUID; type: EntityType; normalized_value: str; display_value: str
    finding_ids: list[UUID]; attributes: dict[str, list[UUID]]; sources: set[str]; is_synthetic: bool

class Relationship(BaseModel):
    id: UUID; investigation_id: UUID; type: RelationType
    source_entity_id: UUID; target_entity_id: UUID
    confidence: float; provenance_kind: ProvenanceKind
    evidence: list[RelationshipEvidence]           # min_length=1
    created_by: str                                # "collector:<name>" | "correlation"
    metadata: dict[str, JsonValue]
    # validator: CORRELATED/INFERRED no pueden ser OBSERVED; POSSIBLY_SAME_AS siempre CORRELATED

class MatchScore(BaseModel):
    left: UUID; right: UUID; features: dict[str, float]; weights: dict[str, float]; score: float

class EntityResolver:
    def __init__(self, cfg: EntityResolutionSection) -> None: ...
    def resolve(self, findings: Sequence[Finding]) -> ResolutionResult: ...   # puro, sin I/O
class ResolutionResult(BaseModel):
    entities: list[Entity]; candidates: list[MatchScore]   # candidates ≥ review_threshold

class CorrelationEngine:
    def __init__(self, cfg: EntityResolutionSection) -> None: ...
    def correlate(self, findings: Sequence[Finding], resolution: ResolutionResult) -> CorrelationResult: ...
class CorrelationResult(BaseModel):
    relationships: list[Relationship]; corroborations: dict[UUID, list[UUID]]; conflicts: list[Conflict]

class CorrelationService:
    async def run(self, investigation_id: UUID) -> CorrelationResult: ...  # escribe entidades, relaciones, outbox
```
Features (valores en [0,1]): `string_similarity` (Jaro-Winkler `rapidfuzz.distance.JaroWinkler.normalized_similarity`),
`shared_context` (comparten target o evidencia), `source_diversity` (fuentes distintas / 3),
`cross_reference` (1.0 si email local-part normalizado == username, o nombre ≈ display name de perfil).

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Mapping: cada `FindingType` mapea a entidad o a atributo (test exhaustivo sobre el enum).
- Merge exacto: dos findings `example.com` de fuentes distintas ⇒ 1 entidad con 2 `finding_ids` y corroboración.
- Ejemplo de SPECS.md §8 (`John Smith`, `john.smith@gmail.com`, `johnsmith`, `example.com`): se crean
  4 entidades, relaciones potenciales CORRELATED con evidencia y **ninguna fusión**.
- Umbrales: score ≥ `link_threshold` ⇒ relación; entre `review` y `link` ⇒ solo candidato; menor ⇒ nada.
  Cambiar el umbral en la config cambia el resultado (sin tocar código).
- Sin transitividad: A≈B y B≈C no crea A≈C.
- `relation_hint` del DNS ⇒ `domain RESOLVES_TO ip` OBSERVED con evidencia = finding.
- Conflicto: dos registradores distintos ⇒ 1 `Conflict` con ambos finding ids.
- Idempotencia del servicio (SQLite): dos ejecuciones ⇒ mismos conteos; filas de outbox por cada alta.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run pytest tests/unit/analyzers tests/unit/services/test_correlation_service.py -q
uv run alembic upgrade head && uv run alembic check
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Escritura en Neo4j (Fase 6), confidence final de relaciones con la fórmula de la Fase 7 (aquí se usa
el `MatchScore` o la confidence del finding origen como valor provisional), UI de revisión de candidatos.

## Riesgos y trampas conocidas
- Explosión combinatoria: comparar solo dentro de cada bloque y limitar con `max_candidates_per_entity`.
- Nombres comunes ("John Smith") generan muchos falsos positivos: `string_similarity` sola nunca basta
  para superar `link_threshold` (peso 0.5 < 0.75), hace falta contexto o referencia cruzada.
- Proveedores de email genéricos (gmail.com…) no son evidencia de relación persona↔dominio.
- No marcar como OBSERVED nada calculado aquí; los tests deben comprobarlo explícitamente.
- Entidades sintéticas y reales nunca deben mezclarse en una misma investigación.
