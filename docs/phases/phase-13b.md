# Fase 13b: Documentación final

## Objetivo
Entregar la documentación completa de SPECS.md §28–29 y §33: README exhaustivo y
`docs/{architecture,collectors,scoring,api,development,security}.md`, con guía para crear
collectors en 4 pasos y sección de ética/limitaciones; documentación sincronizada con el código.

## Dependencias (fases previas y contratos que usa)
- Todas las fases anteriores. `CollectorRegistry.metadata()` (catálogo), `ScoringConfig` (scoring.md),
  OpenAPI (`/api/v1/openapi.json`), `docker-compose.yml` (puertos), `docs/architecture.md` (ADRs).

## Archivos a crear o modificar (rutas exactas)
- `README.md`: propósito, arquitectura, instalación, configuración, ejecución, Docker, collectors, API,
  CLI, scoring, Neo4j, PostgreSQL, desarrollo de plugins, testing, seguridad, limitaciones (SPECS.md §28).
- `docs/collectors.md`: catálogo **generado** (tabla por collector: nombre, descripción, targets, fuente,
  requisitos, API key, rate limit, tipos de datos, `terms_url`) + sección manual de buenas prácticas.
- `docs/scoring.md`: fórmulas de confidence y exposure, tabla de categorías/reglas **generada** desde
  `scoring.yaml`, ejemplo trabajado paso a paso y cómo modificar pesos sin código.
- `docs/api.md`: autenticación (cookie+CSRF, tokens), paginación, errores `Problem`, ejemplos `curl` por recurso.
- `docs/development.md`: entorno local, comandos, convenciones, flujo por fases, **crear un collector en
  4 pasos** (crear → implementar interfaz → registrar (automático/config) → tests), plantilla copiable.
- `docs/security.md`: modelo de amenazas breve, auth/sesiones, secretos, logs, borrado total, endurecimiento
  para producción (cambiar credenciales dev-only, TLS, backups) y **Uso ético y limitaciones** (SPECS.md §33).
- `docs/architecture.md`: actualizar diagrama y ADRs si alguna fase los cambió (añadir ADR nuevos, no reescribir).
- `scripts/gen_docs.py`: genera las secciones marcadas `<!-- BEGIN GENERATED:collectors -->…<!-- END GENERATED -->`
  y `<!-- BEGIN GENERATED:scoring -->…` ; modo `--check` falla si están desactualizadas.
- `collectors/example_collector.py.template`: plantilla de collector externo (no se descubre por la extensión).
- Tests: `backend/tests/unit/test_docs_in_sync.py` (ejecuta `gen_docs --check`), `test_docs_links.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- La documentación que describe datos del código (catálogo, reglas de scoring) se genera; la prosa es manual.
- Idioma: documentación en español (como SPECS.md); identificadores, nombres de API y código en inglés.
- La sección de ética es obligatoria y aparece enlazada desde README, CLI `--help` (epílogo) y pie de la UI.
- Ejemplos solo con datos reservados (`example.com`, `192.0.2.1`, personas ficticias).

## Interfaces y firmas clave (código)
```python
# scripts/gen_docs.py
def render_collectors_table(metadata: Sequence[CollectorMetadata], config: CollectorsConfig) -> str: ...
def render_scoring_tables(scoring: ScoringConfig) -> str: ...
def replace_generated_block(text: str, block: str, content: str) -> str: ...
def main(argv: Sequence[str] | None = None) -> int: ...   # --check ⇒ 1 si hay diferencias
```
Uso ético (contenido mínimo de `docs/security.md`): destinado a investigación OSINT, threat intelligence,
análisis de exposición, auditorías autorizadas, investigación académica y activos propios o autorizados;
**no** implementa ni debe usarse para explotación, robo de credenciales, bypass de autenticación,
credential stuffing, malware, persistencia, evasión de detección, acceso a sistemas privados, doxxing
ni recopilación deliberada de información privada no pública; el usuario es responsable de la base
legal (p. ej. RGPD) de cada investigación.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- `gen_docs --check` pasa (catálogo y scoring al día con el código y el YAML).
- Todos los enlaces relativos de `README.md` y `docs/*.md` apuntan a ficheros existentes.
- Cada collector registrado aparece en `docs/collectors.md`; cada categoría y regla de scoring en `docs/scoring.md`.
- Los comandos del README existen (`osint --help` lista cada subcomando citado).
- README contiene todas las secciones de SPECS.md §28 (test por encabezados).

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run python ../scripts/gen_docs.py && uv run python ../scripts/gen_docs.py --check
uv run pytest tests/unit/test_docs_in_sync.py tests/unit/test_docs_links.py -q
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
cd ../frontend && npm run build
docker compose up --build -d --wait && docker compose down   # verificación final del criterio §34
```

## Fuera de alcance
Sitio de documentación (MkDocs), traducción a otros idiomas, vídeos o tutoriales interactivos.

## Riesgos y trampas conocidas
- Documentación desincronizada: por eso las partes derivadas del código se generan y se testean.
- No copiar claves, tokens ni salidas reales de investigaciones en ejemplos.
- Revisar que los puertos y credenciales documentados coinciden con `docker-compose.yml` y `.env.example`.
- Checklist final: recorrer SPECS.md §34 punto por punto y enlazar en el README dónde se cumple cada uno.
