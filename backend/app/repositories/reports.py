"""Report metadata persistence (generated in Phase 10)."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.domain.records import Report
from app.models import ReportRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import report_to_domain, report_to_row


class ReportRepository(BaseRepository):
    async def add(self, report: Report) -> None:
        self._session.add(report_to_row(report))
        await self._session.flush()

    async def get(self, report_id: UUID) -> Report | None:
        row = await self._session.get(ReportRow, report_id)
        return report_to_domain(row) if row else None

    async def list_by_investigation(self, investigation_id: UUID) -> list[Report]:
        result = await self._session.scalars(
            sa.select(ReportRow)
            .where(ReportRow.investigation_id == investigation_id)
            .order_by(ReportRow.created_at, ReportRow.id)
        )
        return [report_to_domain(r) for r in result]
