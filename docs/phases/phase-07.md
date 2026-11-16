# Fase 7: Exposure Score + Confidence

## Objetivo
Calcular la confidence (0–1) de cada finding y relación, y el Exposure Score (0–100) de cada
investigación con sus 7 categorías, de forma explicable, reproducible y totalmente dirigida por
`config/scoring.yaml` (SPECS.md §11, §12). Asignar severidad a cada finding para la tabla de la UI.

## Dependencias (fases previas y contratos que usa)
- Fase 1: `ScoringConfig` (`confidence`, `exposure`, `severity`), `AppConfig.scoring_hash`, `ProvenanceKind`.
- Fase 2: columnas `findings.confidence`, `findings.confidence_factors`, `findings.severity`; tablas
  `scores`, `score_contributions`; repositorios.
- Fase 5: `Relationship`, corroboraciones (`CorrelationResult.corroborations`), `MatchScore`.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/domain/score.py`: `ConfidenceBreakdown`, `Contribution`, `CategoryScore`, `ExposureScore`.
- `backend/app/scoring/confidence.py`: `ConfidenceCalculator` (puro) y `ConfidenceService` (I/O).
- `backend/app/scoring/exposure.py`: `ExposureCalculator` (puro) y `ExposureService` (I/O).
- `backend/app/scoring/severity.py`: `severity_for(finding, cfg) -> Severity`.
- `backend/app/repositories/scores.py`: guardar/leer `ExposureScore` con contribuciones.
- `backend/app/services/orchestrator.py`: tras la correlación ⇒ confidence ⇒ exposure (en ese orden).
- Tests: `backend/tests/unit/scoring/test_confidence.py`, `test_exposure.py`, `test_severity.py`,
  `backend/tests/unit/scoring/golden/*.yaml` (casos con resultado calculado a mano),
  `backend/tests/unit/services/test_scoring_pipeline.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-007 / §A.2: fórmula de confidence, caps por provenance y desglose persistido en `confidence_factors`.
- ADR-008 / §A.3: reglas, `max_occurrences`, saturación por categoría, `scoring_hash` en cada `Score`.
- Exposure y Confidence son conceptos separados: ningún código usa uno como sustituto del otro.
- Findings con `metadata.origin == "user_seed"` (Fase 4b) **nunca** contribuyen al Exposure Score.
- Corroboración: cuenta **fuentes** distintas (`Finding.source`), no findings.
- Edad para `freshness`: `now - finding.timestamp` con reloj inyectable.
- Cada cálculo crea un `Score` nuevo (histórico); la UI muestra el último. Nunca se sobreescribe.

## Interfaces y firmas clave (código)
```python
class ConfidenceBreakdown(BaseModel):
    factors: dict[str, float]          # las 5 claves de confidence.weights
    weights: dict[str, float]
    raw: float                         # Σ w·f
    cap: float                         # provenance_caps[kind]
    value: float                       # min(cap, raw), redondeado a 4 decimales

class ConfidenceCalculator:
    def __init__(self, cfg: ConfidenceConfig, now: Callable[[], datetime]) -> None: ...
    def for_finding(self, finding: Finding, evidence_kind: EvidenceKind | None,
                    independent_sources: int, entity_match: float = 1.0) -> ConfidenceBreakdown: ...
    def for_relationship(self, rel: Relationship, evidence: Sequence[Finding]) -> ConfidenceBreakdown: ...

class Contribution(BaseModel):
    category: str; rule_id: str; finding_id: UUID | None; relationship_id: UUID | None
    points: float; explanation: str      # explanation de la regla + valor del finding

class CategoryScore(BaseModel):
    name: str; label: str; max_points: float; raw_points: float; score: float   # score = min(max, raw)
    capped: bool; contributions: list[Contribution]

class ExposureScore(BaseModel):
    investigation_id: UUID; total: float; total_max: float; categories: list[CategoryScore]
    scoring_hash: str; scoring_version: int; computed_at: AwareDatetime; is_synthetic: bool

class ExposureCalculator:
    def __init__(self, cfg: ExposureConfig) -> None: ...
    def compute(self, investigation_id: UUID, findings: Sequence[Finding],
                relationships: Sequence[Relationship], scoring_hash: str, now: datetime) -> ExposureScore: ...
```

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Confidence: caso golden calculado a mano (p. ej. dns + dns_response + 2 fuentes + 10 días) con
  resultado exacto a 4 decimales; INFERRED nunca supera 0.60 aunque todos los factores valgan 1.
- Fuente desconocida ⇒ `source_reliability.default`; sin evidencia ⇒ `evidence_quality.none`.
- Freshness: `age = half_life` ⇒ factor 0.5; half-life por tipo respeta la tabla.
- Exposure: categoría saturada (`capped=True`, `score == max_points`); `max_occurrences` toma las
  mejores aportaciones; `min_confidence` excluye; `metadata_equals` filtra (DMARC `none` vs `reject`).
- `user_seed` no puntúa; reglas `relationship` usan `POSSIBLY_SAME_AS`.
- Explicabilidad: Σ `contributions.points` == `raw_points` en cada categoría; total == Σ `score`; 0 ≤ total ≤ 100.
- Reproducibilidad: mismo input + mismo YAML ⇒ mismo resultado y mismo `scoring_hash`; modificar un peso en
  una copia temporal del YAML cambia el total sin tocar código.
- Severidad: mapeo por tipo y `default`.
- Pipeline (SQLite): tras `orchestrator.run`, existe un `Score` con contribuciones enlazadas a findings reales.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run pytest tests/unit/scoring tests/unit/services/test_scoring_pipeline.py -q
grep -rnE "0\.[0-9]+ *\*|weights *= *\{" app/scoring && echo "REVISAR: posibles pesos hardcodeados" || true
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Endpoints `/api/v1/scores` (Fase 8), visualización del desglose (Fase 9b), scoring de riesgo
"ofensivo" o predicciones sobre la persona.

## Riesgos y trampas conocidas
- Flotantes: redondear solo al presentar/persistir; comparar con `pytest.approx` en tests.
- Doble conteo entre categorías (p. ej. `breach_exposure` en credential e historical) es intencionado
  y explicable; documentarlo en la explicación de la regla.
- Recalcular confidence cambia contribuciones: calcular confidence **antes** del exposure en cada ejecución.
- Findings sintéticos: el `Score` hereda `is_synthetic=True` si alguno lo es.
