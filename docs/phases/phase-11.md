# Fase 11: Informes (HTML, JSON, CSV, PDF)

## Objetivo
Generar informes reproducibles de una investigación en HTML, JSON, CSV y PDF con las 13 secciones de
SPECS.md §19, separando claramente hechos observados de inferencias, y almacenarlos con su hash.

## Dependencias (fases previas y contratos que usa)
- Fase 2: tabla/repositorio `reports`; datos de investigación, targets, findings, evidencias, collector_runs.
- Fase 5: entidades y relaciones. Fase 7: `ExposureScore`, `ConfidenceBreakdown`.
- Fase 8: `POST /reports`, `GET /reports/{id}/download` (hoy devuelven 501). `settings.reports`, `settings.demo.banner`.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/reports/snapshot.py`: `ReportSnapshot` (modelo congelado con todo lo que va al informe).
- `backend/app/reports/builder.py`: `ReportSnapshotBuilder` (lee vía UoW).
- `backend/app/reports/renderers/{base,html,json_renderer,csv_renderer,pdf}.py`.
- `backend/app/reports/templates/{report.html.j2,_section_*.html.j2,report.css}`.
- `backend/app/services/reports.py`: `ReportService.generate(investigation_id, fmt) -> ReportRecord`.
- `backend/app/api/v1/reports.py`: sustituir el 501 por la implementación.
- `backend/pyproject.toml`: nada nuevo (Jinja2 ya está; WeasyPrint en extra `pdf`).
- Tests: `backend/tests/unit/reports/test_snapshot.py`, `test_html.py`, `test_json.py`, `test_csv.py`,
  `test_pdf.py`, `backend/tests/unit/api/test_reports_api.py`; golden en `backend/tests/unit/reports/golden/`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-009: PDF = HTML de la misma plantilla renderizado con WeasyPrint (import perezoso; si falta,
  `ReportFormatUnavailable` ⇒ API 503 con mensaje claro).
- El informe se genera desde un `ReportSnapshot` congelado (con `generated_at`, `scoring_hash`,
  versión del framework) para que sea reproducible: mismo snapshot ⇒ mismo JSON byte a byte.
- Ficheros en `settings.reports.output_dir/<investigation_id>/<report_id>.<ext>`; en BD: formato, ruta,
  tamaño, `sha256`, `generated_at`, `generated_by`. Borrar la investigación borra los ficheros.
- Secciones "Hechos observados" (OBSERVED/DERIVED) e "Inferencias y correlaciones" (INFERRED/CORRELATED) separadas.
- `include_raw_evidence: false` por defecto: el informe muestra hash, fuente y resumen, no el contenido crudo.
- Investigaciones sintéticas: `demo.banner` en cabecera y pie de cada página/fichero (también en CSV y JSON).
- Jinja2 con `autoescape=True` siempre.

## Interfaces y firmas clave (código)
```python
class ReportSnapshot(BaseModel):
    investigation: InvestigationRead; targets: list[Target]
    methodology: list[CollectorMethod]        # nombre, fuente, descripción, terms_url, estado de ejecución
    sources: list[Source]
    observed_findings: list[FindingRead]; inferred_findings: list[FindingRead]
    entities: list[Entity]; relationships: list[Relationship]
    evidence: list[EvidenceSummary]           # id, kind, source, retrieved_at, sha256, source_url
    exposure: ExposureScore | None
    confidence_summary: ConfidenceSummary     # media, distribución por provenance
    timeline: list[TimelineEntry]
    limitations: list[str]                    # fijas + colectores fallidos/omitidos + "solo fuentes públicas"
    collected_from: datetime; collected_to: datetime; generated_at: datetime
    framework_version: str; scoring_hash: str; is_synthetic: bool

class ReportRenderer(Protocol):
    format: ReportFormat; media_type: str; extension: str
    def render(self, snapshot: ReportSnapshot) -> bytes: ...

class ReportService:
    async def generate(self, investigation_id: UUID, fmt: ReportFormat, user_id: UUID | None) -> ReportRecord: ...
    async def open(self, report_id: UUID) -> tuple[ReportRecord, Path]: ...
```
Orden de secciones (HTML/PDF/JSON): 1 Información de la investigación · 2 Objetivos · 3 Metodología ·
4 Fuentes · 5 Findings (observados | inferencias) · 6 Entidades · 7 Relaciones · 8 Evidencias ·
9 Exposure Score (con contribuciones) · 10 Confidence · 11 Timeline · 12 Limitaciones · 13 Timestamp de recopilación.
CSV: ZIP con `findings.csv`, `entities.csv`, `relationships.csv`, `evidence.csv`, `exposure.csv`, `README.txt`.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Snapshot: separa findings por provenance; incluye collectors fallidos en limitaciones.
- JSON: validación contra `ReportSnapshot.model_json_schema()`; golden estable (reloj y uuid fijos).
- HTML: contiene las 13 secciones en orden (buscar `id="section-…"`), escapa `<script>` de un finding,
  muestra el banner sintético cuando procede, las inferencias tienen la etiqueta "Inferencia".
- CSV: cabeceras exactas, UTF-8 con BOM opcional desactivado, protección contra CSV injection
  (valores que empiezan por `= + - @` se prefijan con `'`).
- PDF: `pytest.importorskip("weasyprint")`; genera bytes que empiezan por `%PDF`.
- API: `POST /reports` crea registro y fichero; `download` devuelve `Content-Disposition` y sha256 coincide;
  borrar investigación elimina ficheros.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run pytest tests/unit/reports tests/unit/api/test_reports_api.py -q
uv sync --extra pdf && uv run pytest tests/unit/reports/test_pdf.py -q   # donde Pango esté disponible
uv run osint --local report generate <ID> --format html -o /tmp/r.html
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Plantillas personalizables por el usuario, firma digital de informes, envío por email.

## Riesgos y trampas conocidas
- WeasyPrint en Windows requiere GTK/Pango: no bloquear la fase por ello; el test se salta y Docker lo cubre.
- Informes grandes: paginar tablas y limitar evidencias listadas; no cargar `Evidence.content` en el snapshot.
- Fechas: todo en UTC con zona explícita en el texto.
- Ruta de salida: construirla solo con UUIDs (nunca con nombres del usuario) para evitar path traversal.
