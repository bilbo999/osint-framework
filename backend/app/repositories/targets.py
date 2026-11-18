"""Target persistence."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.domain.target import Target
from app.models import TargetRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import target_to_domain, target_to_row


class TargetRepository(BaseRepository):
    async def add(self, target: Target) -> None:
        self._session.add(target_to_row(target))
        await self._session.flush()

    async def get(self, target_id: UUID) -> Target | None:
        row = await self._session.get(TargetRow, target_id)
        return target_to_domain(row) if row else None

    async def list_by_investigation(self, investigation_id: UUID) -> list[Target]:
        """Ordered so that parents always precede their pivoted children."""
        result = await self._session.scalars(
            sa.select(TargetRow)
            .where(TargetRow.investigation_id == investigation_id)
            .order_by(TargetRow.pivot_depth, TargetRow.created_at, TargetRow.id)
        )
        return [target_to_domain(r) for r in result]
