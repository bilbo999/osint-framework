"""audit_log table. Rows tied to an investigation are removed with it (full deletion)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONType, UTCDateTime


class AuditRow(Base):
    __tablename__ = "audit_log"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    actor: Mapped[str] = mapped_column(sa.String(128))
    action: Mapped[str] = mapped_column(sa.String(64))
    entity_type: Mapped[str | None] = mapped_column(sa.String(32))
    entity_id: Mapped[UUID | None] = mapped_column(sa.Uuid)
    details: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
