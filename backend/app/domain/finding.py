"""Finding: one normalized, traceable piece of information.

Fields from SPECS.md §6 plus provenance additions (see docs/architecture.md, ADR-012):
provenance_kind, raw_value, normalization_steps, derived_from, target_id,
relation_hint and is_synthetic.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    StringConstraints,
    model_validator,
)

from app.domain.enums import EntityType, FindingType, ProvenanceKind, RelationType
from app.domain.evidence import Evidence
from app.domain.source import Slug

FindingText = Annotated[str, StringConstraints(min_length=1, max_length=4096)]

#: Metadata keys containing any of these substrings are rejected (no secrets in findings).
FORBIDDEN_METADATA_KEY_PARTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "api_key",
    "apikey",
    "token",
    "authorization",
    "cookie",
)


class NormalizationStep(BaseModel):
    """One deterministic transformation applied to a value (e.g. "lowercase")."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    operation: Annotated[str, StringConstraints(pattern=r"^[a-z0-9_]{1,64}$")]
    input: str
    output: str


class RelationHint(BaseModel):
    """Relationship stated *by the source* between the finding and a subject entity.

    Example: DNS A record => subject (domain "example.com") RESOLVES_TO finding (IP).
    The finding's entity is always the object of the relation.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    subject_type: EntityType
    subject_value: FindingText
    relation: RelationType


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    id: UUID = Field(default_factory=uuid4)
    type: FindingType
    value: FindingText = Field(description="Value as presented by the source (string form).")
    normalized_value: FindingText
    raw_value: JsonValue = Field(description="Original value exactly as returned by the source.")
    normalization_steps: list[NormalizationStep] = Field(default_factory=list)
    source: Slug
    source_url: Annotated[str, StringConstraints(max_length=2048)] | None = None
    timestamp: AwareDatetime = Field(description="When the data was observed/obtained (UTC).")
    confidence: float = Field(ge=0.0, le=1.0)
    collector: Slug
    investigation_id: UUID
    target_id: UUID | None = None
    evidence_id: UUID | None = None
    provenance_kind: ProvenanceKind
    derived_from: list[UUID] = Field(
        default_factory=list, description="Findings this one was derived/inferred from."
    )
    relation_hint: RelationHint | None = None
    is_synthetic: bool = False
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    #: Transient carrier so `Collector.collect()` can return evidence alongside findings.
    #: Excluded from serialization; the persistence layer stores it and keeps evidence_id.
    evidence: Evidence | None = Field(default=None, exclude=True, repr=False)

    @model_validator(mode="after")
    def _check_contract(self) -> Self:
        self._check_evidence()
        self._check_provenance()
        self._check_normalization_chain()
        self._check_metadata_keys()
        return self

    def _check_evidence(self) -> None:
        if self.evidence is None:
            return
        if self.evidence_id is None:
            # Bypass validate_assignment to avoid re-entering this validator.
            object.__setattr__(self, "evidence_id", self.evidence.id)
        elif self.evidence_id != self.evidence.id:
            raise ValueError("evidence_id does not match attached evidence")
        if self.evidence.investigation_id != self.investigation_id:
            raise ValueError("evidence belongs to a different investigation")
        if self.evidence.is_synthetic and not self.is_synthetic:
            raise ValueError("findings built from synthetic evidence must be is_synthetic")

    def _check_provenance(self) -> None:
        kind = self.provenance_kind
        if kind is ProvenanceKind.OBSERVED:
            if self.evidence_id is None:
                raise ValueError("OBSERVED findings require evidence")
            if self.derived_from:
                raise ValueError("OBSERVED findings cannot be derived_from other findings")
        elif kind is ProvenanceKind.DERIVED:
            if self.evidence_id is None and not self.derived_from:
                raise ValueError("DERIVED findings require evidence or derived_from")
        elif not self.derived_from:
            raise ValueError(f"{kind.value} findings require derived_from")
        if self.id in self.derived_from:
            raise ValueError("a finding cannot be derived from itself")

    def _check_normalization_chain(self) -> None:
        steps = self.normalization_steps
        if not steps:
            if self.normalized_value != self.value:
                raise ValueError("normalized_value differs from value but no steps recorded")
            return
        if steps[0].input != self.value:
            raise ValueError("first normalization step must start from value")
        if steps[-1].output != self.normalized_value:
            raise ValueError("last normalization step must produce normalized_value")
        for previous, current in pairwise(steps):
            if previous.output != current.input:
                raise ValueError("normalization steps are not chained")

    def _check_metadata_keys(self) -> None:
        for key in self.metadata:
            lowered = key.lower().replace("-", "_").replace(" ", "_")
            if any(part in lowered for part in FORBIDDEN_METADATA_KEY_PARTS):
                raise ValueError(f"metadata key {key!r} looks like a secret")

    @property
    def is_fact(self) -> bool:
        """True only for directly observed or deterministically derived data."""
        return self.provenance_kind in {ProvenanceKind.OBSERVED, ProvenanceKind.DERIVED}
