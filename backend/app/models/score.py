"""scores table (computed in Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONType, UTCDateTime


class ScoreRow(Base):
    __tablename__ = "scores"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    exposure: Mapped[float] = mapped_column(sa.Float)
    confidence: Mapped[float] = mapped_column(sa.Float)
    breakdown: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    config_sha256: Mapped[str | None] = mapped_column(sa.String(64))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)

    __table_args__ = (
        sa.CheckConstraint("exposure >= 0 AND exposure <= 100", name="exposure_range"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
    )
