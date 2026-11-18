"""Relationship persistence (basic; correlation logic arrives in Phase 5)."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.domain.records import Relationship
from app.models import RelationshipRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import relationship_to_domain, relationship_to_row


class RelationshipRepository(BaseRepository):
    async def add(self, relationship: Relationship) -> None:
        self._session.add(relationship_to_row(relationship))
        await self._session.flush()

    async def get(self, relationship_id: UUID) -> Relationship | None:
        row = await self._session.get(RelationshipRow, relationship_id)
        return relationship_to_domain(row) if row else None

    async def list_by_investigation(
        self, investigation_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Relationship]:
        result = await self._session.scalars(
            sa.select(RelationshipRow)
            .where(RelationshipRow.investigation_id == investigation_id)
            .order_by(RelationshipRow.created_at, RelationshipRow.id)
            .limit(limit)
            .offset(offset)
        )
        return [relationship_to_domain(r) for r in result]
