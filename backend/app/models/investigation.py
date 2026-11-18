"""investigations table. Every other aggregate hangs from it with ON DELETE CASCADE."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime, enum_column
from app.domain.enums import InvestigationStatus


class InvestigationRow(Base):
    __tablename__ = "investigations"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(sa.String(200))
    description: Mapped[str | None] = mapped_column(sa.Text)
    status: Mapped[InvestigationStatus] = mapped_column(enum_column(InvestigationStatus))
    is_synthetic: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    owner_id: Mapped[UUID | None] = mapped_column(sa.Uuid)  # FK to users arrives in Phase 8
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime)
    closed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    __table_args__ = (sa.Index("ix_investigations_status", "status"),)
