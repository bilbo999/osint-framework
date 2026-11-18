"""Evidence persistence."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa

from app.domain.evidence import Evidence
from app.models import EvidenceRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import evidence_to_domain, evidence_to_row


class EvidenceRepository(BaseRepository):
    async def add(
        self,
        evidence: Evidence,
        *,
        content: str | None = None,
        metadata: dict[str, Any] | None = None,
        created_at: datetime | None = None,
    ) -> None:
        """Insert evidence. `content` overrides the stored text (used when truncating)."""
        self._session.add(
            evidence_to_row(evidence, content=content, metadata=metadata, created_at=created_at)
        )
        await self._session.flush()

    async def get(self, evidence_id: UUID) -> Evidence | None:
        row = await self._session.get(EvidenceRow, evidence_id)
        return evidence_to_domain(row) if row else None

    async def get_metadata(self, evidence_id: UUID) -> dict[str, Any] | None:
        row = await self._session.get(EvidenceRow, evidence_id)
        return dict(row.meta) if row else None

    async def existing_ids(self, ids: Collection[UUID]) -> set[UUID]:
        if not ids:
            return set()
        result = await self._session.scalars(
            sa.select(EvidenceRow.id).where(EvidenceRow.id.in_(list(ids)))
        )
        return set(result)

    async def list_by_investigation(
        self, investigation_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[Evidence]:
        result = await self._session.scalars(
            sa.select(EvidenceRow)
            .where(EvidenceRow.investigation_id == investigation_id)
            .order_by(EvidenceRow.retrieved_at, EvidenceRow.id)
            .limit(limit)
            .offset(offset)
        )
        return [evidence_to_domain(r) for r in result]
