"""Audit log persistence (append-only)."""

from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa

from app.domain.records import AuditEvent
from app.models import AuditRow
from app.repositories.base import BaseRepository
from app.repositories.mappers import audit_to_domain, audit_to_row


class AuditRepository(BaseRepository):
    async def add(self, event: AuditEvent) -> None:
        self._session.add(audit_to_row(event))
        await self._session.flush()

    async def list_by_investigation(
        self, investigation_id: UUID, *, limit: int = 100, offset: int = 0
    ) -> list[AuditEvent]:
        result = await self._session.scalars(
            sa.select(AuditRow)
            .where(AuditRow.investigation_id == investigation_id)
            .order_by(AuditRow.created_at, AuditRow.id)
            .limit(limit)
            .offset(offset)
        )
        return [audit_to_domain(r) for r in result]

    async def list_by_action(self, action: str, *, limit: int = 100) -> list[AuditEvent]:
        result = await self._session.scalars(
            sa.select(AuditRow)
            .where(AuditRow.action == action)
            .order_by(AuditRow.created_at, AuditRow.id)
            .limit(limit)
        )
        return [audit_to_domain(r) for r in result]
