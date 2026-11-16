# Fase 4b: Collectors de IP, email, username, URL, teléfono y semillas

## Objetivo
Completar los collectors iniciales de SPECS.md §5: IP (reverse DNS, ASN, organización, país
aproximado), email (sintaxis, dominio, MX, Gravatar, exposición en brechas vía API legítima),
username (presencia en servicios con API pública documentada), URL (dominio, subdominio, TLD, IP,
tecnologías solo si es legítimo), teléfono (validación offline) y pivots desde semillas de persona/organización.

## Dependencias (fases previas y contratos que usa)
- Fase 1: `Collector`, `TargetSeeds`, `collectors.yaml` (entradas ya definidas), `api_key_env`.
- Fase 3: executor (SKIPPED sin API key), pivots del orchestrator, `raise_for_status_mapped`.
- Fase 4a: normalizadores, `DnsResolver`, `builtin/sources.py`, fixtures DNS/HTTP falsas.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/collectors/builtin/{reverse_dns,rdap_ip,cymru_asn,geoip_maxmind}.py`
- `backend/app/collectors/builtin/{email_basics,gravatar,hibp_breaches}.py`
- `backend/app/collectors/builtin/{username_github,username_gitlab}.py`
- `backend/app/collectors/builtin/{url_analysis,http_technologies,phone_basics,seed_pivot}.py`
- `backend/app/collectors/adapters/hibp.py`: `HibpClient` (protocolo), `HttpHibpClient`, `MockHibpClient`.
- `backend/app/collectors/adapters/geoip.py`: `GeoIpReader` (protocolo), `MaxMindReader` (import perezoso), `MockGeoIpReader`.
- `backend/app/collectors/builtin/sources.py`: añadir `team_cymru`, `maxmind_geolite2`, `gravatar`, `hibp`,
  `github_api`, `gitlab_api`, `http_public` (con `homepage_url` y `terms_url` reales de cada servicio).
- `backend/app/demo/data/hibp_mock.json`, `backend/app/demo/data/geoip_mock.json` (sintéticos).
- Tests: `backend/tests/unit/collectors/builtin/test_<collector>.py` (uno por collector).

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-005/012: API keys solo vía `deps.api_key` (`api_key_env`: `OSINT_HIBP_API_KEY`, `OSINT_GITHUB_TOKEN`
  opcional ⇒ `requires_api_key=False` pero lo usa si existe). Nunca en evidencia, metadata ni logs.
- ADR-010: los adaptadores con clave reciben `deps.http_client` (en demo, con `DemoTransport` de la Fase 12)
  y tienen un `Mock*` inyectable por el parámetro `client` (tests). Sin clave y fuera de demo ⇒ `SKIPPED`.
- Minimización (SPECS.md §20/§33): de perfiles públicos guardar solo `login`, `profile_url`, `created_at`,
  contadores públicos; `name/company/location/blog` solo si `options.include_profile_fields: true`.
- HIBP devuelve **nombres de brechas y clases de datos**, nunca credenciales; no se consulta Pwned Passwords.
- `seed_pivot`: emite findings DERIVED (`evidence.kind=computed`) con `metadata.origin="user_seed"`;
  esos findings **no puntúan** en Exposure (Fase 7) y crean targets hijo vía pivots de la Fase 3.
- `http_technologies`: un único GET a la URL dada por el usuario (máx. 3 redirecciones, 64 KiB leídos),
  solo cabeceras `Server`, `X-Powered-By` y `<meta name="generator">`. Desactivado por defecto.

## Interfaces y firmas clave (código)
```python
class HibpClient(Protocol):
    async def breached_account(self, account: str) -> list[HibpBreach]: ...   # [] si 404

class HibpBreach(BaseModel):
    name: str; title: str; domain: str | None; breach_date: date; data_classes: list[str]; is_verified: bool

class HibpBreachesCollector(Collector):
    name = "hibp_breaches"; requires_api_key = True; api_key_env = "OSINT_HIBP_API_KEY"
    supported_targets = frozenset({TargetType.EMAIL}); data_types = frozenset({FindingType.BREACH_EXPOSURE})
    def __init__(self, config: CollectorConfig, deps: CollectorDependencies | None = None,
                 client: HibpClient | None = None) -> None: ...

class GeoIpReader(Protocol):
    def lookup(self, ip: str) -> GeoIpRecord | None: ...   # country_iso, city?, accuracy_radius_km
```
| name | source | targets | data_types (provenance) |
|---|---|---|---|
| reverse_dns | dns | ip_address | reverse_dns, domain (OBSERVED, `HAS_PTR`) |
| rdap_ip | rdap | ip_address | network_registration, organization, geolocation (país de registro) |
| cymru_asn | team_cymru | ip_address | autonomous_system (`ANNOUNCED_BY`) |
| geoip_maxmind | maxmind_geolite2 | ip_address | geolocation (aprox., con `accuracy_radius_km`) |
| email_basics | local_parser + dns | email | email_validation, domain (DERIVED), mx_record |
| gravatar | gravatar | email | gravatar_profile (SHA-256 del email normalizado) |
| hibp_breaches | hibp | email | breach_exposure (`metadata.older_than_5_years`) |
| username_github / username_gitlab | github_api / gitlab_api | username | account_presence |
| url_analysis | local_parser + dns | url | domain, subdomain, tld (DERIVED), ip_address (OBSERVED) |
| http_technologies | http_public | url | technology |
| phone_basics | local_parser | phone | phone (E.164, DERIVED), phone_metadata |
| seed_pivot | local_parser | person, organization | person_name, username, email, phone, domain (DERIVED) |

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Un fichero por collector con `respx`/`FakeResolver`/mocks: caso positivo, "no encontrado" (404/NXDOMAIN ⇒
  `[]`), 429 con `Retry-After` ⇒ `RateLimitedError`, 5xx ⇒ transitorio, JSON inesperado ⇒ permanente.
- HIBP: la cabecera `hibp-api-key` se envía y **no** aparece en la evidencia; `MockHibpClient` funciona sin red.
- Gravatar: hash SHA-256 de `normalize_email` (no MD5); 404 ⇒ sin finding.
- GitHub/GitLab: solo se guardan campos permitidos; con `include_profile_fields=false` no hay `name`/`location`.
- URL: `https://a.b.example.co.uk:443/x` ⇒ domain `example.co.uk`, subdomain `a.b.example.co.uk`, tld `co.uk`,
  pasos `remove_default_port`; sin red para TLD (tldextract offline).
- Phone: `+1 555 0100 123` ⇒ E.164 y región; número inválido ⇒ `phone_metadata` con `valid=false` y sin `phone`.
- seed_pivot: findings con `origin="user_seed"`; sin semillas ⇒ `[]`.
- Registro: los 13 collectors nuevos + 5 de la Fase 4a se descubren; `geoip_maxmind` y `http_technologies`
  quedan fuera de `build_enabled` con la config por defecto.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run pytest tests/unit/collectors/builtin -q
uv run python -c "from app.core.config import get_config; from app.collectors import create_registry; \
from app.core.settings import REPO_ROOT; r=create_registry(get_config().collectors, REPO_ROOT); print(len(r), r.names())"
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Scraping de perfiles HTML, comprobación de username en sitios sin API pública, login en servicios,
Pwned Passwords, búsqueda de personas en buscadores, enriquecimiento de teléfonos con APIs de pago.

## Riesgos y trampas conocidas
- La API de GitHub sin token permite 60 req/h: el rate limit de `collectors.yaml` debe respetarlo.
- GitLab `users?username=` devuelve lista: vacía ⇒ no existe; no confundir con error.
- Team Cymru vía DNS: consulta `origin.asn.cymru.com` (IPv4 invertida) y `asnN.asn.cymru.com` para el nombre.
- Geolocalización por IP es aproximada: confidence baja (`maxmind_geolite2: 0.60`) y texto "aproximada" en UI.
- `seed_pivot` podría inflar el score con datos que el usuario introdujo: por eso `origin="user_seed"`.
- No incluir emails/usernames reales en fixtures: usar `example.org`, `alex-example`, etc.
