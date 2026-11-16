# Fase 4a: Normalizadores + collectors de dominio

## Objetivo
Implementar los normalizadores con trazabilidad (`NormalizationStep`) y los collectors de dominio
de SPECS.md §5: DNS (A/AAAA/CNAME/MX/NS/TXT), SPF y DMARC, WHOIS vía RDAP, certificado TLS público,
Certificate Transparency y subdominios desde CT. Todo con fuentes públicas y consultas de solo lectura.

## Dependencias (fases previas y contratos que usa)
- Fase 1: `Collector` (`new_evidence`, `new_finding`, `validate_output`), `RelationHint`, `FindingType`,
  `EntityType`, `RelationType`, `collectors.yaml` (entradas `dns_records`, `mail_security`, `rdap_domain`,
  `tls_certificate`, `crtsh` ya configuradas).
- Fase 3: `CollectorDependencies.http_client`, `raise_for_status_mapped`, errores, executor.

## Archivos a crear o modificar (rutas exactas)
- `backend/app/analyzers/normalizers.py`: `normalize_domain`, `normalize_email`, `normalize_ip`,
  `normalize_url`, `normalize_username`, `normalize_phone`, `registrable_domain`.
- `backend/app/collectors/dns.py`: protocolo `DnsResolver`, `DnspythonResolver`, `DnsAnswer`.
- `backend/app/collectors/tls.py`: protocolo `TlsFetcher`, `SocketTlsFetcher` (handshake, sin enviar datos).
- `backend/app/collectors/base.py`: añadir `dns_resolver: DnsResolver | None` y `tls_fetcher: TlsFetcher | None`
  a `CollectorDependencies` (campos opcionales; no romper firmas).
- `backend/app/collectors/deps.py`: inyectar resolver y fetcher por defecto.
- `backend/app/collectors/builtin/sources.py`: constantes `Source` (`dns`, `rdap`, `tls`, `crtsh`, `local_parser`).
- `backend/app/collectors/builtin/{dns_records,mail_security,rdap_domain,tls_certificate,crtsh}.py`.
- `backend/tests/fixtures/responses/{rdap_example_com.json,crtsh_example_com.json,...}` (sintéticos).
- `backend/tests/fixtures/fake_dns.py` (`FakeResolver`), `backend/tests/fixtures/fake_tls.py` (`FakeTlsFetcher`).
- Tests: `backend/tests/unit/analyzers/test_normalizers.py`, `backend/tests/unit/collectors/builtin/test_<collector>.py`.

## Decisiones de diseño ya tomadas (referencia a docs/architecture.md)
- ADR-012: cada finding OBSERVED lleva `Evidence` (respuesta DNS/RDAP/CT serializada sin secretos).
  SPF y DMARC son DERIVED (parseo determinista del TXT) con la misma evidencia del TXT.
- Relaciones que afirma la fuente van en `relation_hint` (p. ej. `domain RESOLVES_TO ip`,
  `domain MAIL_HANDLED_BY mx`, `domain NAME_SERVED_BY ns`, `domain HAS_SUBDOMAIN sub`, `domain HAS_CERTIFICATE cert`).
- Normalización: el valor original queda en `value`/`raw_value`; cada transformación es un paso.
  Operaciones con nombres estables: `strip`, `lowercase`, `strip_trailing_dot`, `idna_encode`,
  `strip_wildcard`, `compress_ipv6`, `e164`, `remove_default_port`, `sort_query`.
- `registrable_domain` usa `tldextract` con snapshot PSL incluido (`suffix_list_urls=()`): sin red.
- RDAP en lugar de WHOIS por puerto 43 (JSON estructurado, bootstrap IANA en `options.bootstrap_url`).

## Interfaces y firmas clave (código)
```python
@dataclass(frozen=True)
class NormalizedValue:
    value: str
    steps: list[NormalizationStep]

def normalize_domain(raw: str) -> NormalizedValue: ...     # " WWW.Example.COM. " -> "www.example.com"
def registrable_domain(hostname: str) -> str | None: ...   # "a.b.example.co.uk" -> "example.co.uk"

class DnsAnswer(BaseModel):
    name: str; rdtype: str; ttl: int | None; records: list[str]; nameserver: str | None

class DnsResolver(Protocol):
    async def resolve(self, name: str, rdtype: str) -> DnsAnswer: ...   # NXDOMAIN/NoAnswer -> records=[]

class TlsFetcher(Protocol):
    async def fetch_certificate(self, host: str, port: int, timeout: float) -> bytes: ...  # DER del leaf

class DnsRecordsCollector(Collector):
    name = "dns_records"; supported_targets = frozenset({TargetType.DOMAIN})
    data_types = frozenset({FindingType.IP_ADDRESS, FindingType.DOMAIN, FindingType.SUBDOMAIN,
                            FindingType.MX_RECORD, FindingType.NS_RECORD, FindingType.TXT_RECORD})
    async def collect(self, target: Target) -> list[Finding]: ...
```
Metadatos por collector (tipos emitidos):
| name | source | targets | data_types |
|---|---|---|---|
| dns_records | dns | domain | ip_address, domain, subdomain, mx_record, ns_record, txt_record |
| mail_security | dns | domain | spf_policy, dmarc_policy (DERIVED) |
| rdap_domain | rdap | domain | domain_registration, organization, ns_record |
| tls_certificate | tls | domain | certificate |
| crtsh | crtsh | domain | certificate, subdomain |

`domain_registration.metadata`: `registrar`, `created`, `expires`, `status`, `registrant_redacted` (bool).
`dmarc_policy.metadata.policy` ∈ {`none`,`quarantine`,`reject`,`absent`}; `certificate.metadata`:
`serial`, `issuer`, `not_before`, `not_after`, `sans`, `expired` (bool, con `deps.clock`), `sha256`.

## Tests requeridos (unitarios, integración; sin APIs externas reales)
- Normalizadores: tabla de casos (mayúsculas, punto final, IDN `münchen.de`→`xn--mnchen-3ya.de`, IPv6
  comprimida, URL con puerto por defecto, wildcard `*.example.com`); cadena de pasos válida para `Finding`.
- Cada collector con `FakeResolver`/`respx`/`FakeTlsFetcher` y fixtures sintéticas de `example.com`/`*.example`:
  findings esperados, `relation_hint`, evidencia adjunta, `validate_output` pasa.
- NXDOMAIN ⇒ lista vacía + `SUCCESS`; timeout DNS ⇒ `TransientCollectorError`; RDAP 404 ⇒ vacío;
  crt.sh 502 ⇒ transitorio; JSON inválido ⇒ `PermanentCollectorError`.
- SPF: `v=spf1 include:_spf.example.net -all` ⇒ mecanismos y `all="-all"`; DMARC ausente ⇒ `policy="absent"`.
- crt.sh: deduplicar subdominios, quitar wildcard, ignorar nombres fuera del dominio objetivo.
- Registro: `create_registry(config.collectors, REPO_ROOT)` descubre los 5 collectors.

## Criterios de aceptación verificables (comandos concretos)
```bash
cd backend
uv run pytest tests/unit/analyzers tests/unit/collectors -q
uv run python -c "from app.core.config import get_config; from app.collectors import create_registry; \
from app.core.settings import REPO_ROOT; print(create_registry(get_config().collectors, REPO_ROOT).names())"
uv run pytest -q && uv run ruff check . && uv run black --check . && uv run mypy
```

## Fuera de alcance
Collectors de IP, email, username, URL, teléfono y persona (Fase 4b). Enumeración activa de
subdominios (fuerza bruta DNS, AXFR): **prohibida**. Escaneo de puertos: **prohibido**.

## Riesgos y trampas conocidas
- TXT con varias cadenas: concatenar sin espacios antes de parsear SPF/DMARC.
- crt.sh es lento y devuelve 5xx con frecuencia: respetar `rate_limit` 1/5 s y `timeout_seconds: 30`.
- Bootstrap RDAP: cachear en memoria por proceso; no descargarlo en cada llamada.
- `ssl`: `check_hostname=False` y `CERT_NONE` solo para LEER el certificado de cualquier host; nunca
  enviar datos tras el handshake. Registrar en metadata si la validación habría fallado.
- No meter el certificado PEM completo en `metadata` (va en `Evidence.content`).
- `dnspython` async: usar `dns.asyncresolver`; tiempo de espera desde `config.timeout_seconds`.
