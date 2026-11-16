"""Collector contract (SPECS.md §4).

A collector is a stateless adapter over ONE public source. It:
  * declares its metadata as class attributes (validated by `metadata()`);
  * receives a Target and returns normalized `Finding` objects (with attached Evidence);
  * NEVER touches the database, the graph, the scoring engine or other collectors;
  * NEVER emits INFERRED/CORRELATED findings (that is the correlation engine's job);
  * performs only legitimate, read-only queries on public sources (SPECS.md §33).

Resilience (timeout, retry, backoff, rate limit, circuit breaker) is applied from the
outside by app.collectors.resilience; collectors just raise the errors in
app.collectors.errors.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Annotated, ClassVar

import httpx
from pydantic import BaseModel, ConfigDict, Field, JsonValue, SecretStr, StringConstraints

from app.collectors.errors import CollectorContractError
from app.core.config import CollectorConfig
from app.domain.enums import COLLECTOR_PROVENANCE, FindingType, ProvenanceKind, TargetType
from app.domain.evidence import Evidence, EvidenceKind
from app.domain.finding import Finding, NormalizationStep, RelationHint
from app.domain.rate_limit import RateLimit
from app.domain.source import Slug, Source
from app.domain.target import Target


class CollectorMetadata(BaseModel):
    """Validated, serializable description of a collector (served by /api/v1/collectors)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Slug
    description: Annotated[str, StringConstraints(min_length=1, max_length=512)]
    version: str
    supported_targets: frozenset[TargetType] = Field(min_length=1)
    source: Source
    additional_sources: tuple[Source, ...] = ()
    requirements: tuple[str, ...] = ()
    requires_api_key: bool
    api_key_env: Annotated[str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]+$")] | None
    rate_limit: RateLimit
    data_types: frozenset[FindingType] = Field(min_length=1)

    def source_names(self) -> frozenset[str]:
        return frozenset({self.source.name, *(s.name for s in self.additional_sources)})


def _utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(slots=True)
class CollectorDependencies:
    """Injected resources. Built by the executor (Phase 3); fakes in tests.

    Collectors must use `http_client` (shared, pre-configured with the generic
    User-Agent and timeouts) instead of creating their own clients.

    `synthetic=True` (demo mode, ADR-010): transports serve synthetic fixtures, so every
    Evidence/Finding produced is flagged is_synthetic regardless of the declared Source.
    """

    http_client: httpx.AsyncClient | None = None
    api_key: SecretStr | None = None
    clock: Callable[[], datetime] = field(default=_utc_now)
    synthetic: bool = False


class Collector(ABC):
    """Base class for every collector. Subclasses set ALL the ClassVars below."""

    name: ClassVar[str]
    description: ClassVar[str]
    version: ClassVar[str] = "1.0.0"
    supported_targets: ClassVar[frozenset[TargetType]]
    source: ClassVar[Source]
    additional_sources: ClassVar[tuple[Source, ...]] = ()
    requirements: ClassVar[tuple[str, ...]] = ()
    requires_api_key: ClassVar[bool] = False
    api_key_env: ClassVar[str | None] = None
    rate_limit: ClassVar[RateLimit]
    data_types: ClassVar[frozenset[FindingType]]

    def __init__(
        self,
        config: CollectorConfig,
        deps: CollectorDependencies | None = None,
    ) -> None:
        self.config = config
        self.deps = deps or CollectorDependencies()

    # ------------------------------------------------------------------ metadata
    @classmethod
    def metadata(cls) -> CollectorMetadata:
        """Validate and return class metadata. Raises CollectorContractError if invalid."""
        required = (
            "name",
            "description",
            "supported_targets",
            "source",
            "rate_limit",
            "data_types",
        )
        missing = [attr for attr in required if not hasattr(cls, attr)]
        if missing:
            raise CollectorContractError(f"{cls.__qualname__} is missing metadata: {missing}")
        if cls.requires_api_key != (cls.api_key_env is not None):
            raise CollectorContractError(
                f"{cls.__qualname__}: requires_api_key and api_key_env must be set together"
            )
        try:
            return CollectorMetadata(
                name=cls.name,
                description=cls.description,
                version=cls.version,
                supported_targets=cls.supported_targets,
                source=cls.source,
                additional_sources=cls.additional_sources,
                requirements=cls.requirements,
                requires_api_key=cls.requires_api_key,
                api_key_env=cls.api_key_env,
                rate_limit=cls.rate_limit,
                data_types=cls.data_types,
            )
        except ValueError as exc:
            raise CollectorContractError(f"{cls.__qualname__}: invalid metadata: {exc}") from exc

    @property
    def effective_rate_limit(self) -> RateLimit:
        return self.config.rate_limit or self.rate_limit

    def supports(self, target: Target) -> bool:
        return target.type in self.supported_targets

    # ------------------------------------------------------------------ contract
    @abstractmethod
    async def collect(self, target: Target) -> list[Finding]:
        """Query the source for `target` and return normalized findings.

        Must raise app.collectors.errors.* on failure instead of returning partial junk.
        """

    def validate_output(self, target: Target, findings: Iterable[Finding]) -> list[Finding]:
        """Enforce the output contract. Called by the executor on every result."""
        meta = self.metadata()
        allowed_sources = meta.source_names()
        checked: list[Finding] = []
        for finding in findings:
            problems: list[str] = []
            if finding.collector != self.name:
                problems.append(f"collector={finding.collector!r}")
            if finding.source not in allowed_sources:
                problems.append(f"undeclared source {finding.source!r}")
            if finding.type not in self.data_types:
                problems.append(f"undeclared data type {finding.type.value!r}")
            if finding.provenance_kind not in COLLECTOR_PROVENANCE:
                problems.append(f"collectors cannot emit {finding.provenance_kind.value}")
            if finding.investigation_id != target.investigation_id:
                problems.append("wrong investigation_id")
            if finding.target_id != target.id:
                problems.append("wrong target_id")
            if problems:
                raise CollectorContractError(f"{self.name}: invalid finding: {', '.join(problems)}")
            checked.append(finding)
        return checked

    # ------------------------------------------------------------------ helpers
    def new_evidence(
        self,
        target: Target,
        *,
        kind: EvidenceKind,
        content: str,
        content_type: str = "application/json",
        source_url: str | None = None,
        request_summary: str | None = None,
        source: Source | None = None,
    ) -> Evidence:
        src = source or self.source
        return Evidence(
            investigation_id=target.investigation_id,
            kind=kind,
            source=src.name,
            collector=self.name,
            source_url=source_url,
            request_summary=request_summary,
            retrieved_at=self.deps.clock(),
            content_type=content_type,
            content=content,
            is_synthetic=src.is_synthetic or self.deps.synthetic,
        )

    def new_finding(
        self,
        target: Target,
        *,
        type: FindingType,
        value: str,
        raw_value: JsonValue,
        evidence: Evidence | None,
        normalized_value: str | None = None,
        normalization_steps: list[NormalizationStep] | None = None,
        provenance_kind: ProvenanceKind = ProvenanceKind.OBSERVED,
        derived_from: list[Finding] | None = None,
        relation_hint: RelationHint | None = None,
        metadata: dict[str, JsonValue] | None = None,
        source: Source | None = None,
    ) -> Finding:
        """Build a Finding stamped with collector/source/investigation/target/timestamp."""
        src = source or self.source
        return Finding(
            type=type,
            value=value,
            normalized_value=value if normalized_value is None else normalized_value,
            raw_value=raw_value,
            normalization_steps=normalization_steps or [],
            source=src.name,
            source_url=evidence.source_url if evidence else None,
            timestamp=self.deps.clock(),
            confidence=self.config.provisional_confidence,
            collector=self.name,
            investigation_id=target.investigation_id,
            target_id=target.id,
            evidence=evidence,
            provenance_kind=provenance_kind,
            derived_from=[f.id for f in derived_from or []],
            relation_hint=relation_hint,
            is_synthetic=(
                src.is_synthetic or self.deps.synthetic or bool(evidence and evidence.is_synthetic)
            ),
            metadata=metadata or {},
        )
