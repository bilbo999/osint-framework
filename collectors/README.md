# External collector plugins

Drop third-party or local collectors here. This directory is listed in
`config/collectors.yaml` → `discovery.plugin_paths`, so every `*.py` file or package
(with `__init__.py`) is imported and each concrete `app.collectors.base.Collector`
subclass it defines is registered automatically. Files starting with `_` are ignored.

Rules (see `CLAUDE.md` and `docs/architecture.md`, ADR-012):

- public, legitimate sources only; no login, scraping behind access controls or ToS violations;
- return `Finding` objects; never write to PostgreSQL/Neo4j;
- emit only `OBSERVED` or `DERIVED` provenance, with `Evidence` attached;
- read API keys only through `deps.api_key` (declared via `api_key_env`), never hardcode them;
- add tests with mocked HTTP (`respx`) — never hit real APIs in tests.

Built-in collectors live in `backend/app/collectors/builtin/`.
