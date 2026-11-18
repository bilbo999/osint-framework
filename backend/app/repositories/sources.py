"""Source catalogue persistence."""

from __future__ import annotations

from collections.abc import Collection, Sequence

import sqlalchemy as sa

from app.domain.source import Source
from app.models import SourceRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import source_to_domain, source_to_row


class SourceRepository(BaseRepository):
    async def upsert_many(self, sources: Sequence[Source]) -> None:
        for source in sources:
            await self._session.merge(source_to_row(source))
        await self._session.flush()

    async def get(self, name: str) -> Source | None:
        row = await self._session.get(SourceRow, name)
        return source_to_domain(row) if row else None

    async def existing_names(self, names: Collection[str]) -> set[str]:
        if not names:
            return set()
        result = await self._session.scalars(
            sa.select(SourceRow.name).where(SourceRow.name.in_(list(names)))
        )
        return set(result)

    async def list_all(self) -> list[Source]:
        result = await self._session.scalars(sa.select(SourceRow).order_by(SourceRow.name))
        return [source_to_domain(r) for r in result]
