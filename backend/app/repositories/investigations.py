"""Investigation persistence."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa

from app.domain.enums import InvestigationStatus
from app.domain.records import Investigation
from app.models import InvestigationRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import investigation_to_domain, investigation_to_row


class InvestigationRepository(BaseRepository):
    async def add(self, investigation: Investigation) -> None:
        self._session.add(investigation_to_row(investigation))
        await self._session.flush()

    async def get(self, investigation_id: UUID) -> Investigation | None:
        row = await self._session.get(InvestigationRow, investigation_id)
        return investigation_to_domain(row) if row else None

    async def list_all(self, *, limit: int = 100, offset: int = 0) -> list[Investigation]:
        result = await self._session.scalars(
            sa.select(InvestigationRow)
            .order_by(InvestigationRow.created_at.desc(), InvestigationRow.id)
            .limit(limit)
            .offset(offset)
        )
        return [investigation_to_domain(r) for r in result]

    async def set_status(
        self,
        investigation_id: UUID,
        status: InvestigationStatus,
        *,
        now: datetime,
        closed_at: datetime | None = None,
    ) -> None:
        await self._session.execute(
            sa.update(InvestigationRow)
            .where(InvestigationRow.id == investigation_id)
            .values(status=status, updated_at=now, closed_at=closed_at)
        )

    async def delete(self, investigation_id: UUID) -> None:
        """Delete the row; ON DELETE CASCADE removes every dependent row in the database."""
        await self._session.execute(
            sa.delete(InvestigationRow).where(InvestigationRow.id == investigation_id)
        )
