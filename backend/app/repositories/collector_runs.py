"""CollectorRun persistence."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.domain.records import CollectorRun
from app.models import CollectorRunRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import collector_run_to_domain, collector_run_to_row


class CollectorRunRepository(BaseRepository):
    async def add(self, run: CollectorRun) -> None:
        self._session.add(collector_run_to_row(run))
        await self._session.flush()

    async def list_by_investigation(self, investigation_id: UUID) -> list[CollectorRun]:
        result = await self._session.scalars(
            sa.select(CollectorRunRow)
            .where(CollectorRunRow.investigation_id == investigation_id)
            .order_by(CollectorRunRow.created_at, CollectorRunRow.id)
        )
        return [collector_run_to_domain(r) for r in result]
