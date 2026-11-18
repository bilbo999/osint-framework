"""collector_runs table: one row per (collector, target) execution."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, enum_column
from app.domain.enums import CollectorRunStatus


class CollectorRunRow(Base):
    __tablename__ = "collector_runs"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    target_id: Mapped[UUID] = mapped_column(sa.ForeignKey("targets.id", ondelete="CASCADE"))
    collector: Mapped[str] = mapped_column(sa.String(64))
    status: Mapped[CollectorRunStatus] = mapped_column(enum_column(CollectorRunStatus))
    attempts: Mapped[int] = mapped_column(sa.Integer)
    duration_seconds: Mapped[float] = mapped_column(sa.Float)
    findings_count: Mapped[int] = mapped_column(sa.Integer)
    error: Mapped[str | None] = mapped_column(sa.Text)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
