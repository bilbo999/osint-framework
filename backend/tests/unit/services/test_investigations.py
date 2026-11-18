"""InvestigationService: create, duplicate, close/reopen, delete (full cascade)."""

from __future__ import annotations

from collections.abc import Callable
from uuid import uuid4

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.collectors.resilience import CollectorOutcome
from app.db.base import Base
from app.db.uow import UnitOfWork
from app.domain import EntityType, ProvenanceKind, RelationType, Target, TargetSeeds, TargetType
from app.domain.enums import CollectorRunStatus, InvestigationStatus
from app.domain.records import Entity, Relationship, Report, Score
from app.schemas.investigation import TargetCreate
from app.services.errors import InvestigationClosedError, InvestigationNotFoundError
from app.services.investigations import InvestigationService
from app.services.persistence import FindingPersister
from tests.conftest import FIXED_NOW
from tests.fixtures.builders import make_evidence, make_finding, make_source


async def test_create_returns_draft_investigation_and_audits(
    investigation_service: InvestigationService, uow_factory: Callable[[], UnitOfWork]
) -> None:
    inv = await investigation_service.create("Case A", "desc", is_synthetic=True)
    assert inv.status is InvestigationStatus.DRAFT
    assert inv.is_synthetic is True
    assert inv.description == "desc"
    assert inv.created_at == FIXED_NOW
    assert (await investigation_service.get(inv.id)).name == "Case A"
    async with uow_factory() as uow:
        events = await uow.audit.list_by_investigation(inv.id)
    assert [e.action for e in events] == ["investigation.created"]


async def test_add_target_validates_and_persists(
    investigation_service: InvestigationService, uow_factory: Callable[[], UnitOfWork]
) -> None:
    inv = await investigation_service.create("c", None)
    target = await investigation_service.add_target(
        inv.id,
        TargetCreate(
            type=TargetType.PERSON,
            value="Alex Example",
            seeds=TargetSeeds(first_name="Alex"),
        ),
    )
    async with uow_factory() as uow:
        assert await uow.targets.get(target.id) == target
    with pytest.raises(ValueError, match="not a valid"):
        await investigation_service.add_target(
            inv.id, TargetCreate(type=TargetType.DOMAIN, value="not a domain")
        )
    with pytest.raises(InvestigationNotFoundError):
        await investigation_service.add_target(
            uuid4(), TargetCreate(type=TargetType.DOMAIN, value="example.com")
        )


async def test_duplicate_copies_targets_with_new_ids_but_not_findings(
    investigation_service: InvestigationService,
    uow_factory: Callable[[], UnitOfWork],
    persister: FindingPersister,
) -> None:
    inv = await investigation_service.create("orig", "d")
    t1 = await investigation_service.add_target(
        inv.id, TargetCreate(type=TargetType.DOMAIN, value="example.com")
    )
    t2 = await investigation_service.add_target(
        inv.id,
        TargetCreate(
            type=TargetType.PERSON, value="Alex Example", seeds=TargetSeeds(first_name="Alex")
        ),
    )
    # A pivoted child target must keep pointing to the COPY of its parent.
    async with uow_factory() as uow:
        child = Target(
            investigation_id=inv.id,
            type=TargetType.EMAIL,
            value="alex@example.com",
            parent_target_id=t2.id,
            pivot_depth=1,
            created_at=FIXED_NOW,
        )
        await uow.targets.add(child)
        await uow.commit()
    finding = make_finding(inv.id, evidence=make_evidence(inv.id), target_id=t1.id)
    await persister.persist(
        CollectorOutcome(
            collector="dns_records",
            target_id=t1.id,
            status=CollectorRunStatus.SUCCESS,
            findings=[finding],
        ),
        [make_source("dns")],
    )

    copy = await investigation_service.duplicate(inv.id, "copy")
    assert copy.id != inv.id
    assert copy.name == "copy"
    assert copy.status is InvestigationStatus.DRAFT
    async with uow_factory() as uow:
        originals = await uow.targets.list_by_investigation(inv.id)
        copies = await uow.targets.list_by_investigation(copy.id)
        assert await uow.findings.count_by_investigation(copy.id) == 0
        assert await uow.findings.count_by_investigation(inv.id) == 1
        assert await uow.evidence.list_by_investigation(copy.id) == []
        assert await uow.collector_runs.list_by_investigation(copy.id) == []
    assert {t.id for t in originals}.isdisjoint({t.id for t in copies})
    assert sorted((t.type, t.value) for t in copies) == sorted((t.type, t.value) for t in originals)
    new_person = next(t for t in copies if t.type is TargetType.PERSON)
    new_child = next(t for t in copies if t.type is TargetType.EMAIL)
    assert new_person.seeds == t2.seeds
    assert new_child.parent_target_id == new_person.id
    assert new_child.pivot_depth == 1


async def test_close_makes_investigation_read_only_and_reopen_restores(
    investigation_service: InvestigationService,
    persister: FindingPersister,
) -> None:
    inv = await investigation_service.create("c", None)
    target = await investigation_service.add_target(
        inv.id, TargetCreate(type=TargetType.DOMAIN, value="example.com")
    )
    await investigation_service.close(inv.id)
    closed = await investigation_service.get(inv.id)
    assert closed.status is InvestigationStatus.CLOSED
    assert closed.closed_at == FIXED_NOW
    await investigation_service.close(inv.id)  # idempotent
    with pytest.raises(InvestigationClosedError):
        await investigation_service.add_target(
            inv.id, TargetCreate(type=TargetType.DOMAIN, value="example.org")
        )
    with pytest.raises(InvestigationClosedError):
        await persister.persist(
            CollectorOutcome(
                collector="dns_records", target_id=target.id, status=CollectorRunStatus.SUCCESS
            ),
            [],
        )
    await investigation_service.reopen(inv.id)
    reopened = await investigation_service.get(inv.id)
    assert reopened.status is InvestigationStatus.DRAFT
    assert reopened.closed_at is None
    await investigation_service.add_target(
        inv.id, TargetCreate(type=TargetType.DOMAIN, value="example.org")
    )


async def test_reopen_after_runs_goes_back_to_completed(
    investigation_service: InvestigationService, persister: FindingPersister
) -> None:
    inv = await investigation_service.create("c", None)
    target = await investigation_service.add_target(
        inv.id, TargetCreate(type=TargetType.DOMAIN, value="example.com")
    )
    await persister.persist(
        CollectorOutcome(
            collector="dns_records", target_id=target.id, status=CollectorRunStatus.SUCCESS
        ),
        [],
    )
    await investigation_service.close(inv.id)
    await investigation_service.reopen(inv.id)
    assert (await investigation_service.get(inv.id)).status is InvestigationStatus.COMPLETED


async def test_missing_investigation_raises(investigation_service: InvestigationService) -> None:
    for call in (
        investigation_service.close(uuid4()),
        investigation_service.reopen(uuid4()),
        investigation_service.delete(uuid4()),
        investigation_service.duplicate(uuid4(), "x"),
        investigation_service.get(uuid4()),
    ):
        with pytest.raises(InvestigationNotFoundError):
            await call


async def test_delete_removes_every_row_and_queues_graph_cleanup(
    investigation_service: InvestigationService,
    uow_factory: Callable[[], UnitOfWork],
    persister: FindingPersister,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    keep = await investigation_service.create("keep", None)
    inv = await investigation_service.create("doomed", None)
    target = await investigation_service.add_target(
        inv.id, TargetCreate(type=TargetType.DOMAIN, value="example.com")
    )
    await persister.persist(
        CollectorOutcome(
            collector="dns_records",
            target_id=target.id,
            status=CollectorRunStatus.SUCCESS,
            findings=[make_finding(inv.id, evidence=make_evidence(inv.id), target_id=target.id)],
        ),
        [make_source("dns")],
    )
    async with uow_factory() as uow:
        a = Entity(
            investigation_id=inv.id,
            type=EntityType.DOMAIN,
            normalized_value="example.com",
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
        b = Entity(
            investigation_id=inv.id,
            type=EntityType.IP_ADDRESS,
            normalized_value="192.0.2.1",
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
        await uow.entities.add(a)
        await uow.entities.add(b)
        await uow.relationships.add(
            Relationship(
                investigation_id=inv.id,
                source_entity_id=a.id,
                target_entity_id=b.id,
                type=RelationType.RESOLVES_TO,
                confidence=0.9,
                provenance_kind=ProvenanceKind.DERIVED,
                created_at=FIXED_NOW,
            )
        )
        await uow.scores.add(
            Score(investigation_id=inv.id, exposure=1, confidence=0.5, created_at=FIXED_NOW)
        )
        await uow.reports.add(
            Report(investigation_id=inv.id, format="html", title="t", created_at=FIXED_NOW)
        )
        await uow.commit()

    await investigation_service.delete(inv.id)

    investigation_scoped = [
        t.name
        for t in Base.metadata.sorted_tables
        if "investigation_id" in t.c and t.name != "graph_outbox"
    ]
    assert {"targets", "evidence", "findings", "entities", "relationships", "scores"} <= set(
        investigation_scoped
    )
    async with session_factory() as session:
        for name in investigation_scoped:
            table = Base.metadata.tables[name]
            count = await session.scalar(
                sa.select(sa.func.count())
                .select_from(table)
                .where(table.c.investigation_id == inv.id)
            )
            assert count == 0, f"residual rows in {name}"
        assert (
            await session.scalar(
                sa.select(sa.func.count()).select_from(Base.metadata.tables["investigations"])
            )
            == 1
        )
    async with uow_factory() as uow:
        assert await uow.investigations.get(keep.id) is not None
        (event,) = await uow.outbox.list_by_investigation(inv.id)
        assert event.operation == "delete_investigation"
        assert event.aggregate_id == inv.id
        assert event.processed_at is None
        (audit,) = await uow.audit.list_by_action("investigation.deleted")
        assert audit.entity_id == inv.id
        assert audit.investigation_id is None
