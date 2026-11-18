"""targets table."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import NullableJSONType, UTCDateTime, enum_column
from app.domain.enums import TargetType


class TargetRow(Base):
    __tablename__ = "targets"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    type: Mapped[TargetType] = mapped_column(enum_column(TargetType))
    value: Mapped[str] = mapped_column(sa.String(2048))
    seeds: Mapped[dict[str, Any] | None] = mapped_column(NullableJSONType)
    parent_target_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("targets.id", ondelete="SET NULL")
    )
    pivot_depth: Mapped[int] = mapped_column(sa.Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
