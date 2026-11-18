"""Investigation lifecycle: create, add targets, duplicate, close/reopen, delete."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.db.uow import UnitOfWork
from app.domain.enums import InvestigationStatus
from app.domain.records import AuditEvent, Investigation, OutboxEvent
from app.domain.target import Target
from app.schemas.investigation import InvestigationRead, TargetCreate
from app.services.errors import InvestigationClosedError, InvestigationNotFoundError

DELETE_INVESTIGATION_OPERATION = "delete_investigation"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class InvestigationService:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._uow_factory = uow_factory
        self._clock = clock

    async def create(
        self, name: str, description: str | None, is_synthetic: bool = False
    ) -> InvestigationRead:
        now = self._clock()
        investigation = Investigation(
            name=name,
            description=description,
            is_synthetic=is_synthetic,
            created_at=now,
            updated_at=now,
        )
        async with self._uow_factory() as uow:
            await uow.investigations.add(investigation)
            await self._audit(uow, "investigation.created", investigation.id)
            await uow.commit()
        return InvestigationRead.from_domain(investigation)

    async def get(self, investigation_id: UUID) -> InvestigationRead:
        async with self._uow_factory() as uow:
            investigation = await self._get(uow, investigation_id)
        return InvestigationRead.from_domain(investigation)

    async def add_target(self, investigation_id: UUID, target: TargetCreate) -> Target:
        async with self._uow_factory() as uow:
            await self._get_open(uow, investigation_id)
            created = Target(
                investigation_id=investigation_id,
                type=target.type,
                value=target.value,
                seeds=target.seeds,
                created_at=self._clock(),
            )
            await uow.targets.add(created)
            await self._audit(
                uow, "target.added", investigation_id, entity_type="target", entity_id=created.id
            )
            await uow.commit()
        return created

    async def duplicate(self, investigation_id: UUID, new_name: str) -> InvestigationRead:
        """Copy the investigation and its targets (new ids). Findings are NOT copied."""
        now = self._clock()
        async with self._uow_factory() as uow:
            source = await self._get(uow, investigation_id)
            copy = Investigation(
                name=new_name,
                description=source.description,
                is_synthetic=source.is_synthetic,
                owner_id=source.owner_id,
                created_at=now,
                updated_at=now,
            )
            await uow.investigations.add(copy)
            id_map: dict[UUID, UUID] = {}
            for old in await uow.targets.list_by_investigation(investigation_id):  # parents first
                new_id = uuid4()
                id_map[old.id] = new_id
                parent = id_map.get(old.parent_target_id) if old.parent_target_id else None
                await uow.targets.add(
                    old.model_copy(
                        update={
                            "id": new_id,
                            "investigation_id": copy.id,
                            "parent_target_id": parent,
                            "pivot_depth": old.pivot_depth if parent else 0,
                            "created_at": now,
                        }
                    )
                )
            await self._audit(
                uow,
                "investigation.duplicated",
                copy.id,
                details={"source_investigation_id": str(investigation_id)},
            )
            await uow.commit()
        return InvestigationRead.from_domain(copy)

    async def close(self, investigation_id: UUID) -> None:
        async with self._uow_factory() as uow:
            investigation = await self._get(uow, investigation_id)
            if investigation.status is InvestigationStatus.CLOSED:
                return
            now = self._clock()
            await uow.investigations.set_status(
                investigation_id, InvestigationStatus.CLOSED, now=now, closed_at=now
            )
            await self._audit(uow, "investigation.closed", investigation_id)
            await uow.commit()

    async def reopen(self, investigation_id: UUID) -> None:
        """CLOSED -> COMPLETED if collectors already ran, otherwise DRAFT."""
        async with self._uow_factory() as uow:
            investigation = await self._get(uow, investigation_id)
            if investigation.status is not InvestigationStatus.CLOSED:
                return
            ran = await uow.collector_runs.list_by_investigation(investigation_id)
            status = InvestigationStatus.COMPLETED if ran else InvestigationStatus.DRAFT
            await uow.investigations.set_status(
                investigation_id, status, now=self._clock(), closed_at=None
            )
            await self._audit(uow, "investigation.reopened", investigation_id)
            await uow.commit()

    async def delete(self, investigation_id: UUID) -> None:
        """Delete EVERYTHING (DB cascade) and queue 'delete_investigation' for the graph."""
        async with self._uow_factory() as uow:
            await self._get(uow, investigation_id)
            await uow.investigations.delete(investigation_id)
            await uow.outbox.add(
                OutboxEvent(
                    operation=DELETE_INVESTIGATION_OPERATION,
                    aggregate_type="investigation",
                    aggregate_id=investigation_id,
                    investigation_id=investigation_id,
                    created_at=self._clock(),
                )
            )
            # Not tied to the investigation (its rows are gone): only the id is kept.
            await uow.audit.add(
                AuditEvent(
                    action="investigation.deleted",
                    entity_type="investigation",
                    entity_id=investigation_id,
                    created_at=self._clock(),
                )
            )
            await uow.commit()

    # ------------------------------------------------------------------ helpers
    @staticmethod
    async def _get(uow: UnitOfWork, investigation_id: UUID) -> Investigation:
        investigation = await uow.investigations.get(investigation_id)
        if investigation is None:
            raise InvestigationNotFoundError(investigation_id)
        return investigation

    async def _get_open(self, uow: UnitOfWork, investigation_id: UUID) -> Investigation:
        investigation = await self._get(uow, investigation_id)
        if investigation.status is InvestigationStatus.CLOSED:
            raise InvestigationClosedError(investigation_id)
        return investigation

    async def _audit(
        self,
        uow: UnitOfWork,
        action: str,
        investigation_id: UUID,
        *,
        entity_type: str | None = None,
        entity_id: UUID | None = None,
        details: dict[str, str] | None = None,
    ) -> None:
        await uow.audit.add(
            AuditEvent(
                investigation_id=investigation_id,
                action=action,
                entity_type=entity_type or "investigation",
                entity_id=entity_id or investigation_id,
                details=dict(details or {}),
                created_at=self._clock(),
            )
        )
