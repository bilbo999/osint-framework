"""Entity persistence (basic; resolution logic arrives in Phase 5)."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.domain.enums import EntityType
from app.domain.records import Entity
from app.models import EntityRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import entity_to_domain, entity_to_row


class EntityRepository(BaseRepository):
    async def add(self, entity: Entity) -> None:
        self._session.add(entity_to_row(entity))
        await self._session.flush()

    async def get(self, entity_id: UUID) -> Entity | None:
        row = await self._session.get(EntityRow, entity_id)
        return entity_to_domain(row) if row else None

    async def list_by_investigation(
        self,
        investigation_id: UUID,
        *,
        types: set[EntityType] | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Entity]:
        stmt = sa.select(EntityRow).where(EntityRow.investigation_id == investigation_id)
        if types:
            stmt = stmt.where(EntityRow.type.in_(sorted(types)))
        stmt = stmt.order_by(EntityRow.created_at, EntityRow.id).limit(limit).offset(offset)
        return [entity_to_domain(r) for r in await self._session.scalars(stmt)]
