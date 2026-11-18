"""evidence table. Never stores request headers; content is capped by the persister."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONType, UTCDateTime, enum_column
from app.domain.evidence import EvidenceKind


class EvidenceRow(Base):
    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(sa.Uuid, primary_key=True)
    investigation_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("investigations.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[EvidenceKind] = mapped_column(enum_column(EvidenceKind))
    source: Mapped[str] = mapped_column(sa.ForeignKey("sources.name"))
    collector: Mapped[str] = mapped_column(sa.String(64))
    source_url: Mapped[str | None] = mapped_column(sa.String(2048))
    request_summary: Mapped[str | None] = mapped_column(sa.String(2048))
    retrieved_at: Mapped[datetime] = mapped_column(UTCDateTime)
    content_type: Mapped[str] = mapped_column(sa.String(255))
    content: Mapped[str] = mapped_column(sa.Text)
    #: sha256 of the ORIGINAL content (differs from the stored content when truncated).
    sha256: Mapped[str] = mapped_column(sa.String(64))
    is_synthetic: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    meta: Mapped[dict[str, Any]] = mapped_column("metadata", JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
