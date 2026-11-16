"""Typed loader for the non-sensitive configuration in config/*.yaml.

    settings.yaml   -> SettingsConfig    (app, logging, execution, security, ER, graph, ...)
    collectors.yaml -> CollectorsConfig  (discovery, defaults, per-collector overrides)
    scoring.yaml    -> ScoringConfig     (confidence factors, exposure categories, severity)

Secrets never live here; they come from environment variables (app.core.settings).
All numeric weights/thresholds used by the engines MUST be read from these models.
"""

from __future__ import annotations

import hashlib
import math
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal, Self

import yaml
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    model_validator,
)

from app.domain.enums import (
    EntityType,
    FindingType,
    ProvenanceKind,
    RelationType,
    Severity,
)
from app.domain.rate_limit import RateLimit

Unit = Annotated[float, Field(ge=0.0, le=1.0)]
WEIGHT_TOLERANCE = 1e-6


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _require_all_provenance(mapping: dict[ProvenanceKind, float], name: str) -> None:
    missing = set(ProvenanceKind) - set(mapping)
    if missing:
        raise ValueError(f"{name} missing provenance kinds: {sorted(missing)}")


# =============================================================================== settings.yaml
class AppSection(_Strict):
    name: str
    environment: Literal["development", "test", "production"]
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=list)


class LoggingSection(_Strict):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]
    format: Literal["json", "console"]
    redact_keys: list[str]


class ExecutionSection(_Strict):
    backend: Literal["arq", "inline"]
    max_concurrent_collectors: PositiveInt
    investigation_timeout_seconds: PositiveFloat
    max_pivot_depth: Annotated[int, Field(ge=0, le=3)]
    pivot_finding_types: list[FindingType]
    max_findings_per_collector: PositiveInt
    progress_poll_interval_seconds: PositiveFloat


class SecuritySection(_Strict):
    session_cookie_name: str
    session_idle_timeout_minutes: PositiveInt
    session_absolute_timeout_hours: PositiveInt
    csrf_header_name: str
    password_min_length: Annotated[int, Field(ge=12)]
    api_rate_limit_per_minute: PositiveInt
    login_rate_limit_per_minute: PositiveInt
    api_token_prefix: str


class HttpSection(_Strict):
    user_agent: str
    connect_timeout_seconds: PositiveFloat
    verify_tls: bool
    max_response_bytes: PositiveInt


class EvidenceSection(_Strict):
    max_content_bytes: PositiveInt
    store_raw_content: bool


class EntityResolutionSection(_Strict):
    auto_merge_entity_types: list[EntityType]
    never_auto_merge_entity_types: list[EntityType]
    similarity_algorithm: Literal["jaro_winkler", "levenshtein", "token_set"]
    feature_weights: dict[str, Unit]
    link_threshold: Unit
    review_threshold: Unit
    max_candidates_per_entity: PositiveInt

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not math.isclose(sum(self.feature_weights.values()), 1.0, abs_tol=WEIGHT_TOLERANCE):
            raise ValueError("entity_resolution.feature_weights must sum to 1.0")
        if self.review_threshold >= self.link_threshold:
            raise ValueError("review_threshold must be lower than link_threshold")
        overlap = set(self.auto_merge_entity_types) & set(self.never_auto_merge_entity_types)
        if overlap:
            raise ValueError(f"entity types both auto-merge and never-merge: {sorted(overlap)}")
        return self


class GraphSection(_Strict):
    max_expand_depth: Annotated[int, Field(ge=1, le=6)]
    max_nodes_returned: PositiveInt
    default_min_confidence: Unit
    outbox_batch_size: PositiveInt


class ReportsSection(_Strict):
    formats: list[Literal["html", "json", "csv", "pdf"]]
    include_raw_evidence: bool
    output_dir: str


class DemoSection(_Strict):
    enabled: bool
    dataset_dir: str
    banner: str


class SettingsConfig(_Strict):
    app: AppSection
    logging: LoggingSection
    execution: ExecutionSection
    security: SecuritySection
    http: HttpSection
    evidence: EvidenceSection
    entity_resolution: EntityResolutionSection
    graph: GraphSection
    reports: ReportsSection
    demo: DemoSection


# ============================================================================= collectors.yaml
class RetryConfig(_Strict):
    max_attempts: Annotated[int, Field(ge=1, le=10)]
    backoff_base_seconds: PositiveFloat
    backoff_max_seconds: PositiveFloat
    jitter: Unit
    retry_on_status: list[int] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.backoff_max_seconds < self.backoff_base_seconds:
            raise ValueError("backoff_max_seconds must be >= backoff_base_seconds")
        return self


class CircuitBreakerConfig(_Strict):
    failure_threshold: PositiveInt
    recovery_timeout_seconds: PositiveFloat
    half_open_max_calls: PositiveInt


class CollectorConfig(_Strict):
    """Fully-resolved configuration for one collector instance."""

    enabled: bool
    timeout_seconds: PositiveFloat
    provisional_confidence: Unit
    retry: RetryConfig
    circuit_breaker: CircuitBreakerConfig
    rate_limit: RateLimit | None = Field(
        default=None, description="None => use the collector class' declared rate_limit."
    )
    options: dict[str, JsonValue] = Field(default_factory=dict)


class CollectorOverride(_Strict):
    """Partial per-collector entry in collectors.yaml; unset fields inherit defaults."""

    enabled: bool | None = None
    timeout_seconds: PositiveFloat | None = None
    provisional_confidence: Unit | None = None
    retry: dict[str, Any] | None = None
    circuit_breaker: dict[str, Any] | None = None
    rate_limit: RateLimit | None = None
    options: dict[str, JsonValue] = Field(default_factory=dict)


class DiscoveryConfig(_Strict):
    packages: list[str]
    modules: list[str] = Field(default_factory=list)
    plugin_paths: list[str] = Field(default_factory=list)
    entry_points: bool = True
    entry_point_group: str = "osint_framework.collectors"


class CollectorsConfig(_Strict):
    discovery: DiscoveryConfig
    defaults: CollectorConfig
    collectors: dict[str, CollectorOverride] = Field(default_factory=dict)

    def resolve(self, name: str) -> CollectorConfig:
        """Merge defaults with the override for `name` (unknown names get defaults)."""
        override = self.collectors.get(name)
        if override is None:
            return self.defaults
        base = self.defaults.model_dump()
        for key, value in override.model_dump(exclude_unset=True).items():
            if isinstance(value, dict) and isinstance(base.get(key), dict):
                base[key] = {**base[key], **value}
            else:
                base[key] = value
        return CollectorConfig.model_validate(base)


# ================================================================================ scoring.yaml
class CorroborationConfig(_Strict):
    saturation_sources: PositiveInt


class FreshnessConfig(_Strict):
    default_half_life_days: PositiveFloat
    half_life_days: dict[FindingType, PositiveFloat] = Field(default_factory=dict)


class ConfidenceConfig(_Strict):
    weights: dict[
        Literal[
            "source_reliability", "evidence_quality", "entity_match", "corroboration", "freshness"
        ],
        Unit,
    ]
    provenance_caps: dict[ProvenanceKind, Unit]
    source_reliability: dict[str, Unit]
    evidence_quality: dict[str, Unit]
    corroboration: CorroborationConfig
    freshness: FreshnessConfig

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(self.weights) != 5:
            raise ValueError("confidence.weights must define all five factors")
        if not math.isclose(sum(self.weights.values()), 1.0, abs_tol=WEIGHT_TOLERANCE):
            raise ValueError("confidence.weights must sum to 1.0")
        _require_all_provenance(self.provenance_caps, "confidence.provenance_caps")
        for table_name, table in (
            ("source_reliability", self.source_reliability),
            ("evidence_quality", self.evidence_quality),
        ):
            if "default" not in table:
                raise ValueError(f"confidence.{table_name} needs a 'default' entry")
        return self


class ExposureRule(_Strict):
    id: Annotated[str, Field(pattern=r"^[a-z_]+\.[a-z0-9_]+$")]
    kind: Literal["finding", "relationship"] = "finding"
    finding_types: list[FindingType] = Field(default_factory=list)
    relationship_types: list[RelationType] = Field(default_factory=list)
    metadata_equals: dict[str, JsonValue] = Field(default_factory=dict)
    points: PositiveFloat
    max_occurrences: PositiveInt
    explanation: str

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.kind == "finding" and not self.finding_types:
            raise ValueError(f"rule {self.id}: finding rules need finding_types")
        if self.kind == "relationship" and not self.relationship_types:
            raise ValueError(f"rule {self.id}: relationship rules need relationship_types")
        return self


ExposureCategoryName = Literal[
    "identity", "contact", "credential", "social", "infrastructure", "historical", "correlation"
]


class ExposureCategory(_Strict):
    label: str
    description: str
    max_points: PositiveFloat
    rules: list[ExposureRule]


class ExposureConfig(_Strict):
    total_max: PositiveFloat
    min_confidence: Unit
    provenance_multipliers: dict[ProvenanceKind, NonNegativeFloat]
    categories: dict[ExposureCategoryName, ExposureCategory]

    @model_validator(mode="after")
    def _check(self) -> Self:
        if len(self.categories) != 7:
            raise ValueError("exposure.categories must define all seven categories")
        total = sum(c.max_points for c in self.categories.values())
        if not math.isclose(total, self.total_max, abs_tol=WEIGHT_TOLERANCE):
            raise ValueError(f"category max_points sum to {total}, expected {self.total_max}")
        _require_all_provenance(self.provenance_multipliers, "exposure.provenance_multipliers")
        ids = [r.id for c in self.categories.values() for r in c.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("exposure rule ids must be unique")
        for name, category in self.categories.items():
            if any(not r.id.startswith(f"{name}.") for r in category.rules):
                raise ValueError(f"rule ids in category {name} must start with '{name}.'")
        return self


class SeverityConfig(_Strict):
    default: Severity
    by_finding_type: dict[FindingType, Severity] = Field(default_factory=dict)


class ScoringConfig(_Strict):
    version: PositiveInt
    confidence: ConfidenceConfig
    exposure: ExposureConfig
    severity: SeverityConfig


# ===================================================================================== loading
class AppConfig(_Strict):
    settings: SettingsConfig
    collectors: CollectorsConfig
    scoring: ScoringConfig
    scoring_hash: str = Field(description="sha256 of scoring.yaml; stored with every Score.")
    config_dir: Path


def _read_yaml(path: Path) -> tuple[dict[str, Any], bytes]:
    raw = path.read_bytes()
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a YAML mapping")
    return data, raw


def load_config(config_dir: Path) -> AppConfig:
    settings, _ = _read_yaml(config_dir / "settings.yaml")
    collectors, _ = _read_yaml(config_dir / "collectors.yaml")
    scoring, scoring_raw = _read_yaml(config_dir / "scoring.yaml")
    return AppConfig(
        settings=SettingsConfig.model_validate(settings),
        collectors=CollectorsConfig.model_validate(collectors),
        scoring=ScoringConfig.model_validate(scoring),
        scoring_hash=hashlib.sha256(scoring_raw).hexdigest(),
        config_dir=config_dir,
    )


@lru_cache(maxsize=1)
def get_config() -> AppConfig:
    """Process-wide config, located via OSINT_CONFIG_DIR (see app.core.settings)."""
    from app.core.settings import get_env_settings

    return load_config(get_env_settings().config_dir)
