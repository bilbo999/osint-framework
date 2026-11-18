"""reports table (generated in Phase 10)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class ReportRow(Base):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    format: Mapped[str] = mapped_column(sa.String(16))
    title: Mapped[str] = mapped_column(sa.String(256))
    file_path: Mapped[str | None] = mapped_column(sa.String(1024))
    sha256: Mapped[str | None] = mapped_column(sa.String(64))
    is_synthetic: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
