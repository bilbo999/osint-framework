# CLAUDE.md

## Propósito
Framework OSINT modular para analizar la exposición digital de un objetivo (persona, organización,
dominio, IP, email, username, teléfono, URL) usando **solo fuentes públicas y APIs legítimas**:
recopila, normaliza, correlaciona, grafica, puntúa (Exposure 0–100 + Confidence 0–1) e informa.

## Documentos
- `docs/SPECS.md` — especificación funcional (fuente de verdad de requisitos).
- `docs/architecture.md` — capas y ADRs (decisiones ya tomadas; no reabrirlas sin un ADR nuevo).
- `docs/phases/phase-NN[a|b].md` — alcance, firmas, tests y criterios de cada fase (02…13b).
- `config/{settings,collectors,scoring}.yaml` — configuración no sensible; secretos solo en `.env`.
- `collectors/README.md` — plugins externos. `README.md` — visión general.

## Comandos (requiere `uv` y Node ≥ 22; en Windows usar Git Bash)
```bash
cd backend && uv sync                      # crea .venv con Python 3.12 y dependencias dev
uv run uvicorn app.main:app --reload       # API en :8000  (GET /api/v1/health)
uv run pytest -q                           # tests (integración se salta sin OSINT_TEST_*)
uv run pytest -m integration -q            # con servicios reales
uv run ruff check .                        # lint   (ruff check --fix . para autocorregir)
uv run black --check .                     # formato (black . para aplicar)
uv run mypy                                # tipos (strict)
cd frontend && npm ci && npm run dev       # UI en :5173 (proxy /api -> :8000)
cd frontend && npm run build               # tsc -b + vite build
scripts/check.sh                           # todas las comprobaciones de backend y frontend
docker compose up --build                  # entorno completo (a partir de la Fase 13a)
```

## Convenciones de código
- Python 3.12, tipado estricto (mypy strict), Pydantic v2, SQLAlchemy 2.x async, línea 100 (Black + Ruff).
- Capas: `api → services → collectors|analyzers|scoring|graph|reports → repositories → models → domain`.
  `app/domain` no importa nada del resto; los objetos ORM no salen de `app/repositories`.
- Contratos en `app/domain`; DTOs de API en `app/schemas`; ORM en `app/models`.
- Todo peso, umbral o límite se lee de `config/*.yaml` vía `app.core.config`; nunca literales en código.
- Fechas siempre con zona horaria UTC; ids `UUID`; enums `StrEnum` (no renombrar valores existentes).
- Dependencias externas inyectadas (`CollectorDependencies`, `deps.clock`) para testear sin red.
- Tests junto a cada cambio: `backend/tests/unit/...` espejo de `app/...`; nunca contra APIs reales.
- Datos de ejemplo/fixtures solo con valores reservados (`example.com`, `192.0.2.0/24`, `+1 555 01xx`).

## Reglas inquebrantables
1. Sin API keys, contraseñas ni secretos en código, config YAML, fixtures, logs ni commits (`.env` está ignorado).
2. Los collectors **no escriben** en PostgreSQL/Neo4j: devuelven `Finding` (+`Evidence`); persiste `FindingPersister`.
3. Nunca presentar una inferencia como dato `OBSERVED`: collectors solo emiten OBSERVED/DERIVED; INFERRED y
   CORRELATED exigen `derived_from` y se rotulan como inferencia en API, UI e informes.
4. No avanzar de fase si la anterior está rota (tests, ruff, black, mypy o arranque fallan).
5. Solo fuentes públicas y legítimas, respetando sus términos y rate limits; sin login ni scraping tras controles.
6. Sin actividad ofensiva: nada de explotación, fuerza bruta, escaneo de puertos, credential stuffing,
   bypass de autenticación, evasión, malware ni doxxing (SPECS.md §33).
7. No inventar APIs externas ni credenciales: si una fuente necesita clave, adaptador + mock + `SKIPPED` sin clave.
8. Toda conclusión debe poder rastrearse hasta su `Evidence` (provenance completo).

## Protocolo por fase
1. Leer `docs/phases/phase-NN.md` completo y los ADR que cite; revisar el código existente que usa.
2. Comprobar que la fase anterior está verde (`scripts/check.sh`); si no, arreglarla primero.
3. Implementar solo el alcance de la fase (respetar "Fuera de alcance"); no cambiar firmas públicas
   existentes salvo que la fase lo indique; añadir tests requeridos.
4. Ejecutar tests, ruff, black, mypy y `npm run build`; comprobar arranque (`uvicorn` + `/api/v1/health`).
5. Ejecutar los "Criterios de aceptación" de la fase y anotar desviaciones en `docs/architecture.md` (ADR nuevo).
6. Commit: `Fase N: <título>` (p. ej. `Fase 4a: normalizadores y collectors de dominio`).

## Estado
- Fase 1 (arquitectura y contratos): completada.
- Fase 2 (backend + modelos + PostgreSQL): completada. Siguiente: `docs/phases/phase-03.md`.
