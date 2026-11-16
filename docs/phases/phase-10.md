# Fase 10: CLI (Typer)

## Objetivo
Ofrecer una CLI `osint` que cubra los casos de uso de SPECS.md §18 usando exactamente la API REST
(remota o en proceso), sin duplicar lógica: investigaciones, objetivos, escaneo con progreso,
collectors, findings, grafo, informes, login y export JSON.

## Dependencias (fases previas y contratos que usa)
- Fase 8: todos los endpoints `/api/v1/*`, tokens personales `osk_…` (Bearer), `Problem`.
- Fase 1: `app/cli/main.py` (Typer app con `version`), entry point `osint` en `pyproject.toml`.
- Fase 8: `app/cli/admin.py` (`osint admin create-user`) ya existe; se registra como subcomando.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/cli/client.py`: `ApiClient` (httpx; modo remoto o `ASGITransport`).
- `backend/app/cli/config.py`: perfil en `~/.config/osint/config.toml` (Windows: `%APPDATA%\osint\config.toml`).
- `backend/app/cli/output.py`: tablas (`rich`, ya dependencia de Typer) y salida `--json`.
- `backend/app/cli/commands/{auth,investigation,target,scan,collectors,findings,graph,report,demo}.py`.
- `backend/app/cli/main.py`: registrar subcomandos y opciones globales.
- Tests: `backend/tests/unit/cli/test_<grupo>.py`, `backend/tests/unit/cli/conftest.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-011: `--api-url URL` (por defecto el del perfil) o `--local` (ASGI en proceso con `create_app()`).
- Credenciales: token guardado en el fichero de perfil con permisos 0600 (en Windows, carpeta de usuario);
  alternativa `OSINT_API_TOKEN` en entorno. Nunca se imprime el token tras crearlo salvo una vez.
- Salida humana por defecto; `--json` imprime exactamente la respuesta de la API (útil para scripts).
- Códigos de salida: 0 ok, 1 error de uso/validación, 2 error de API (4xx), 3 servidor/red, 4 escaneo con avisos.
- El modo `--local` requiere `DATABASE_URL` y ejecuta con `execution.backend: inline`.

## Interfaces y firmas clave (código)
```python
class ApiClient:
    def __init__(self, base_url: str | None, token: SecretStr | None, *, local: bool = False) -> None: ...
    async def request(self, method: str, path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any: ...
    async def __aenter__(self) -> "ApiClient": ...
    async def __aexit__(self, *exc: object) -> None: ...
```
Comandos (todos aceptan `--json`):
```bash
osint login [--api-url URL]                       # pide email/contraseña, crea token osk_ y lo guarda
osint logout
osint investigation create NAME [--description TEXT]
osint investigation list | show ID | duplicate ID NAME | close ID | reopen ID | delete ID [--yes] | export ID [-o FILE]
osint target add INVESTIGATION_ID VALUE [--type domain|ip_address|email|username|phone|url|person|organization]
                 [--first-name --last-name --username --email --domain]   # semillas persona/organización
osint scan INVESTIGATION_ID [--collector NAME ...] [--wait/--no-wait]      # --wait muestra progreso
osint collectors list | show NAME | enable NAME | disable NAME | run NAME --target TARGET_ID
osint findings list INVESTIGATION_ID [--type T] [--min-confidence 0.5] [--provenance OBSERVED] [--limit N]
osint graph export INVESTIGATION_ID [--format json|graphml] [-o FILE]
osint report generate INVESTIGATION_ID --format html|json|csv|pdf [-o FILE]
osint demo load                                    # solo con OSINT_DEMO_MODE=true (Fase 12)
osint admin create-user --email EMAIL --role admin|analyst|viewer
osint version
```
`target add` sin `--type` usa la misma heurística de detección que el frontend (implementarla en
`app/domain/validation.py::detect_target_type` y exponerla; el frontend replica la lógica en TS).

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Con `typer.testing.CliRunner` y `--local` sobre SQLite + `InlineJobQueue` + collectors falsos:
  flujo completo `investigation create` → `target add` → `scan --wait` → `findings list --json` → `report generate`.
- `--json` produce JSON válido idéntico a la respuesta de la API (comparar con llamada directa).
- Códigos de salida por caso (404 ⇒ 2, validación ⇒ 1, escaneo con avisos ⇒ 4).
- `login` guarda el token con permisos restringidos (en POSIX, `stat` 0600) y `logout` lo borra.
- `delete` sin `--yes` pide confirmación; con entrada "n" no borra.
- El token nunca aparece en la salida de `--help`, errores ni logs.
- `detect_target_type`: misma tabla de casos que el test del frontend (fixture compartida en `tests/fixtures/target_detection.json`).

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run osint --help && uv run osint investigation --help
uv run pytest tests/unit/cli -q
uv run osint --local investigation create "Prueba" --json
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Shell interactiva/TUI, autocompletado avanzado (el de Typer basta), gestión de usuarios distinta de
`admin create-user`.

## Riesgos y trampas conocidas
- Typer + async: los comandos son síncronos y llaman a `asyncio.run(...)`; no anidar event loops en tests.
- `--local` arranca `create_app()` y su `lifespan`: usar `asgi-lifespan` o invocar el lifespan manualmente
  (httpx `ASGITransport` no ejecuta lifespan por sí solo).
- Rutas de configuración multiplataforma: usar `typer.get_app_dir("osint")`.
- No duplicar validaciones de negocio en la CLI: dejar que la API devuelva 422 y mostrar el `Problem`.
