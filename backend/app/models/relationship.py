"""relationships table (edges between entities)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONType, UTCDateTime, enum_column
from app.domain.enums import ProvenanceKind, RelationType


class RelationshipRow(Base):
    __tablename__ = "relationships"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    source_entity_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    target_entity_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("entities.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[RelationType] = mapped_column(enum_column(RelationType))
    confidence: Mapped[float] = mapped_column(sa.Float)
    provenance_kind: Mapped[ProvenanceKind] = mapped_column(enum_column(ProvenanceKind))
    finding_ids: Mapped[list[str]] = mapped_column(JSONType, default=list)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.UniqueConstraint(
            "investigation_id", "source_entity_id", "target_entity_id", "type", name="edge"
        ),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )
