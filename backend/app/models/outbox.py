"""graph_outbox table (ADR-004): changes to project into Neo4j, written in the same transaction.

`investigation_id` has NO foreign key on purpose: a 'delete_investigation' event must outlive
the rows it describes so the graph can be cleaned up afterwards.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JSONType, UTCDateTime

_BigIntPK = sa.BigInteger().with_variant(sa.Integer(), "sqlite")


class OutboxRow(Base):
    __tablename__ = "graph_outbox"

    id: Mapped[int] = mapped_column(_BigIntPK, primary_key=True, autoincrement=True)
    operation: Mapped[str] = mapped_column(sa.String(64))
    aggregate_type: Mapped[str] = mapped_column(sa.String(32))
    aggregate_id: Mapped[UUID] = mapped_column(sa.Uuid)
    investigation_id: Mapped[UUID] = mapped_column(sa.Uuid, index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime)
    processed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    attempts: Mapped[int] = mapped_column(sa.Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(sa.Text)

    __table_args__ = (sa.Index("ix_graph_outbox_pending", "processed_at", "id"),)
