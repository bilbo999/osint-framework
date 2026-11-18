"""entities table: one table for every entity type (ADR-003)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONType, UTCDateTime, enum_column
from app.domain.enums import EntityType


class EntityRow(Base):
    __tablename__ = "entities"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE")
    )
    type: Mapped[EntityType] = mapped_column(enum_column(EntityType))
    normalized_value: Mapped[str] = mapped_column(sa.Text)
    display_name: Mapped[str | None] = mapped_column(sa.Text)
    confidence: Mapped[float] = mapped_column(sa.Float, default=1.0)
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.Index("ix_entities_investigation_type", "investigation_id", "type"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )
