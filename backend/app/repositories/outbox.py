"""graph_outbox persistence (ADR-004). Consumed by GraphSyncService in Phase 6."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa

from app.domain.records import OutboxEvent
from app.models import OutboxRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import outbox_to_domain, outbox_to_row


class OutboxRepository(BaseRepository):
    async def add(self, event: OutboxEvent) -> None:
        self._session.add(outbox_to_row(event))
        await self._session.flush()

    async def list_pending(self, *, limit: int = 100) -> list[OutboxEvent]:
        result = await self._session.scalars(
            sa.select(OutboxRow)
            .where(OutboxRow.processed_at.is_(None))
            .order_by(OutboxRow.id)
            .limit(limit)
        )
        return [outbox_to_domain(r) for r in result]

    async def list_by_investigation(self, investigation_id: UUID) -> list[OutboxEvent]:
        result = await self._session.scalars(
            sa.select(OutboxRow)
            .where(OutboxRow.investigation_id == investigation_id)
            .order_by(OutboxRow.id)
        )
        return [outbox_to_domain(r) for r in result]

    async def mark_processed(self, event_id: int, *, at: datetime) -> None:
        await self._session.execute(
            sa.update(OutboxRow).where(OutboxRow.id == event_id).values(processed_at=at)
        )
