"""findings table."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONType, NullableJSONType, UTCDateTime, enum_column
from app.domain.enums import FindingType, ProvenanceKind, Severity


class FindingRow(Base):
    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE")
    )
    target_id: Mapped[UUID | None] = mapped_column(sa.ForeignKey("targets.id", ondelete="SET NULL"))
    evidence_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("evidence.id", ondelete="SET NULL")
    )
    type: Mapped[FindingType] = mapped_column(enum_column(FindingType))
    value: Mapped[str] = mapped_column(sa.Text)
    normalized_value: Mapped[str] = mapped_column(sa.Text)
    raw_value: Mapped[Any] = mapped_column(JSONType)
    normalization_steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    source: Mapped[str] = mapped_column(sa.ForeignKey("sources.name"))
    source_url: Mapped[str | None] = mapped_column(sa.String(2048))
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime)
    confidence: Mapped[float] = mapped_column(sa.Float)
    collector: Mapped[str] = mapped_column(sa.String(64))
    provenance_kind: Mapped[ProvenanceKind] = mapped_column(enum_column(ProvenanceKind))
    derived_from: Mapped[list[str]] = mapped_column(JSONType, default=list)
    relation_hint: Mapped[dict[str, Any] | None] = mapped_column(NullableJSONType)
    is_synthetic: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
    # Reserved for Phase 7 (explainable confidence / severity); unused in Phase 2.
    confidence_factors: Mapped[dict[str, Any] | None] = mapped_column(NullableJSONType)
    severity: Mapped[Severity | None] = mapped_column(enum_column(Severity))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.Index("ix_findings_investigation_type", "investigation_id", "type"),
        sa.Index("ix_findings_normalized_value", "normalized_value"),
        sa.Index("ix_findings_target_id", "target_id"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )
