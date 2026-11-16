"""Domain enumerations shared by every layer.

Values are part of the public contract (persisted in PostgreSQL, sent over the API,
referenced from config/*.yaml). Never rename a value; add new ones instead.
"""

from enum import StrEnum


class TargetType(StrEnum):
    """Kind of seed the user asks to investigate."""

    PERSON = "person"
    ORGANIZATION = "organization"
    DOMAIN = "domain"
    IP_ADDRESS = "ip_address"
    EMAIL = "email"
    USERNAME = "username"
    PHONE = "phone"
    URL = "url"


class ProvenanceKind(StrEnum):
    """How a piece of information came to exist (see docs/architecture.md, ADR-012).

    OBSERVED   returned verbatim by a source; backed by an Evidence record.
    DERIVED    deterministic transformation of observed data (e.g. SPF parsed from TXT).
    INFERRED   probabilistic conclusion (e.g. "probably the same person").
    CORRELATED produced by the correlation engine linking several findings.

    Collectors may only emit OBSERVED or DERIVED. INFERRED/CORRELATED are produced by
    app.analyzers and must never be presented as directly observed facts.
    """

    OBSERVED = "OBSERVED"
    DERIVED = "DERIVED"
    INFERRED = "INFERRED"
    CORRELATED = "CORRELATED"


COLLECTOR_PROVENANCE: frozenset[ProvenanceKind] = frozenset(
    {ProvenanceKind.OBSERVED, ProvenanceKind.DERIVED}
)


class FindingType(StrEnum):
    """What a Finding's value represents. Referenced by config/scoring.yaml rules."""

    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    TLD = "tld"
    IP_ADDRESS = "ip_address"
    EMAIL = "email"
    USERNAME = "username"
    PHONE = "phone"
    URL = "url"
    PERSON_NAME = "person_name"
    ORGANIZATION = "organization"
    CERTIFICATE = "certificate"
    MX_RECORD = "mx_record"
    NS_RECORD = "ns_record"
    TXT_RECORD = "txt_record"
    SPF_POLICY = "spf_policy"
    DMARC_POLICY = "dmarc_policy"
    DOMAIN_REGISTRATION = "domain_registration"
    NETWORK_REGISTRATION = "network_registration"
    REVERSE_DNS = "reverse_dns"
    AUTONOMOUS_SYSTEM = "autonomous_system"
    GEOLOCATION = "geolocation"
    EMAIL_VALIDATION = "email_validation"
    PHONE_METADATA = "phone_metadata"
    GRAVATAR_PROFILE = "gravatar_profile"
    ACCOUNT_PRESENCE = "account_presence"
    BREACH_EXPOSURE = "breach_exposure"
    TECHNOLOGY = "technology"


class EntityType(StrEnum):
    """Graph node labels (Neo4j) and rows of the `entities` table (Phase 5/6)."""

    PERSON = "person"
    ORGANIZATION = "organization"
    DOMAIN = "domain"
    SUBDOMAIN = "subdomain"
    IP_ADDRESS = "ip_address"
    EMAIL = "email"
    USERNAME = "username"
    PHONE = "phone"
    URL = "url"
    CERTIFICATE = "certificate"
    AUTONOMOUS_SYSTEM = "autonomous_system"


class RelationType(StrEnum):
    """Relationship types between entities (Neo4j relationship types, upper-case)."""

    OWNS = "OWNS"
    USES = "USES"
    HAS_EMAIL = "HAS_EMAIL"
    HAS_PHONE = "HAS_PHONE"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    RESOLVES_TO = "RESOLVES_TO"
    HAS_PTR = "HAS_PTR"
    HAS_SUBDOMAIN = "HAS_SUBDOMAIN"
    HAS_CERTIFICATE = "HAS_CERTIFICATE"
    MAIL_HANDLED_BY = "MAIL_HANDLED_BY"
    NAME_SERVED_BY = "NAME_SERVED_BY"
    ANNOUNCED_BY = "ANNOUNCED_BY"
    REGISTERED_BY = "REGISTERED_BY"
    HOSTED_ON = "HOSTED_ON"
    POSSIBLY_SAME_AS = "POSSIBLY_SAME_AS"


class CollectorRunStatus(StrEnum):
    """Outcome of one collector execution against one target (Phase 3)."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    RATE_LIMITED = "rate_limited"
    CIRCUIT_OPEN = "circuit_open"
    SKIPPED = "skipped"


class InvestigationStatus(StrEnum):
    """Lifecycle of an investigation. One failed collector => COMPLETED_WITH_WARNINGS."""

    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNINGS = "completed_with_warnings"
    FAILED = "failed"
    CLOSED = "closed"


class Severity(StrEnum):
    """Severity shown in the findings table; mapping lives in config/scoring.yaml."""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
