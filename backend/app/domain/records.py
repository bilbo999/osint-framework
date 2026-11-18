"""Persisted records that are not part of the collector contract (Phase 2).

Repositories return these (never ORM objects). Pure data, no I/O.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, StringConstraints

from app.domain.enums import (
    CollectorRunStatus,
    EntityType,
    InvestigationStatus,
    ProvenanceKind,
    RelationType,
)
from app.domain.source import Slug


def _now() -> datetime:
    return datetime.now(UTC)


class _Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Investigation(_Record):
    id: UUID = Field(default_factory=uuid4)
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: str | None = None
    status: InvestigationStatus = InvestigationStatus.DRAFT
    is_synthetic: bool = False
    owner_id: UUID | None = None
    created_at: AwareDatetime = Field(default_factory=_now)
    updated_at: AwareDatetime = Field(default_factory=_now)
    closed_at: AwareDatetime | None = None


class CollectorRun(_Record):
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    target_id: UUID
    collector: Slug
    status: CollectorRunStatus
    attempts: int = Field(ge=0)
    duration_seconds: float = Field(ge=0)
    findings_count: int = Field(ge=0)
    error: str | None = None
    created_at: AwareDatetime = Field(default_factory=_now)


class Entity(_Record):
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    type: EntityType
    normalized_value: Annotated[str, StringConstraints(min_length=1, max_length=4096)]
    display_name: str | None = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    attributes: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: AwareDatetime = Field(default_factory=_now)
    updated_at: AwareDatetime = Field(default_factory=_now)


class Relationship(_Record):
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    source_entity_id: UUID
    target_entity_id: UUID
    type: RelationType
    confidence: float = Field(ge=0.0, le=1.0)
    provenance_kind: ProvenanceKind
    finding_ids: list[UUID] = Field(default_factory=list)
    created_at: AwareDatetime = Field(default_factory=_now)


class Score(_Record):
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    exposure: float = Field(ge=0.0, le=100.0)
    confidence: float = Field(ge=0.0, le=1.0)
    breakdown: dict[str, JsonValue] = Field(default_factory=dict)
    config_sha256: str | None = None
    created_at: AwareDatetime = Field(default_factory=_now)


class Report(_Record):
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    format: Annotated[str, StringConstraints(pattern=r"^(html|json|csv|pdf)$")]
    title: str
    file_path: str | None = None
    sha256: str | None = None
    is_synthetic: bool = False
    created_at: AwareDatetime = Field(default_factory=_now)


class AuditEvent(_Record):
    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID | None = None
    actor: str = "system"
    action: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    entity_type: str | None = None
    entity_id: UUID | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: AwareDatetime = Field(default_factory=_now)


class OutboxEvent(_Record):
    """Pending change to project into Neo4j (ADR-004). `id` is assigned by the database."""

    id: int | None = None
    operation: Annotated[str, StringConstraints(min_length=1, max_length=64)]
    aggregate_type: Annotated[str, StringConstraints(min_length=1, max_length=32)]
    aggregate_id: UUID
    investigation_id: UUID
    payload: dict[str, JsonValue] = Field(default_factory=dict)
    created_at: AwareDatetime = Field(default_factory=_now)
    processed_at: AwareDatetime | None = None
    attempts: int = 0
    last_error: str | None = None
