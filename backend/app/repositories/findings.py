"""Finding persistence."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

import sqlalchemy as sa

from app.domain.enums import FindingType
from app.domain.finding import Finding
from app.models import FindingRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import finding_to_domain, finding_to_row


class FindingRepository(BaseRepository):
    async def add_many(
        self, findings: Sequence[Finding], *, created_at: datetime | None = None
    ) -> None:
        self._session.add_all([finding_to_row(f, created_at=created_at) for f in findings])
        await self._session.flush()

    async def get(self, finding_id: UUID) -> Finding | None:
        row = await self._session.get(FindingRow, finding_id)
        return finding_to_domain(row) if row else None

    async def list_by_investigation(
        self,
        investigation_id: UUID,
        *,
        types: set[FindingType] | None = None,
        min_confidence: float = 0.0,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Finding]:
        stmt = sa.select(FindingRow).where(
            FindingRow.investigation_id == investigation_id,
            FindingRow.confidence >= min_confidence,
        )
        if types:
            stmt = stmt.where(FindingRow.type.in_(sorted(types)))
        stmt = stmt.order_by(FindingRow.timestamp, FindingRow.id).limit(limit).offset(offset)
        result = await self._session.scalars(stmt)
        return [finding_to_domain(r) for r in result]

    async def count_by_investigation(self, investigation_id: UUID) -> int:
        result = await self._session.scalar(
            sa.select(sa.func.count())
            .select_from(FindingRow)
            .where(FindingRow.investigation_id == investigation_id)
        )
        return int(result or 0)
