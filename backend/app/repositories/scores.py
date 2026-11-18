"""Score persistence (computed in Phase 7)."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.domain.records import Score
from app.models import ScoreRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import score_to_domain, score_to_row


class ScoreRepository(BaseRepository):
    async def add(self, score: Score) -> None:
        self._session.add(score_to_row(score))
        await self._session.flush()

    async def latest(self, investigation_id: UUID) -> Score | None:
        row = await self._session.scalar(
            sa.select(ScoreRow)
            .where(ScoreRow.investigation_id == investigation_id)
            .order_by(ScoreRow.created_at.desc(), ScoreRow.id)
            .limit(1)
        )
        return score_to_domain(row) if row else None

    async def list_by_investigation(self, investigation_id: UUID) -> list[Score]:
        result = await self._session.scalars(
            sa.select(ScoreRow)
            .where(ScoreRow.investigation_id == investigation_id)
            .order_by(ScoreRow.created_at, ScoreRow.id)
        )
        return [score_to_domain(r) for r in result]
