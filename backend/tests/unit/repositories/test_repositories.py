"""Repository behaviour against SQLite (ADR-014)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.uow import UnitOfWork
from app.domain import FindingType, ProvenanceKind, RelationType
from app.domain.enums import EntityType
from app.domain.records import Entity, Investigation, OutboxEvent, Relationship, Report, Score
from tests.conftest import FIXED_NOW
from tests.fixtures.builders import make_evidence, make_finding, make_source


async def _seed(uow: UnitOfWork) -> Investigation:
    inv = Investigation(name="seed", created_at=FIXED_NOW, updated_at=FIXED_NOW)
    await uow.investigations.add(inv)
    await uow.sources.upsert_many([make_source("dns")])
    return inv


async def test_findings_list_filters_by_type_confidence_and_pages(
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    async with uow_factory() as uow:
        inv = await _seed(uow)
        evidence = make_evidence(inv.id)
        await uow.evidence.add(evidence)
        findings = [
            make_finding(inv.id, evidence=evidence, confidence=0.9),
            make_finding(
                inv.id,
                evidence=evidence,
                confidence=0.4,
                type=FindingType.DOMAIN,
                value="example.com",
                normalized_value="example.com",
                normalization_steps=[],
                timestamp=FIXED_NOW + timedelta(seconds=1),
            ),
            make_finding(
                inv.id,
                evidence=evidence,
                confidence=0.7,
                type=FindingType.DOMAIN,
                value="example.org",
                normalized_value="example.org",
                normalization_steps=[],
                timestamp=FIXED_NOW + timedelta(seconds=2),
            ),
        ]
        await uow.findings.add_many(findings)
        await uow.commit()
    async with uow_factory() as uow:
        everything = await uow.findings.list_by_investigation(inv.id)
        assert [f.id for f in everything] == [f.id for f in findings]
        domains = await uow.findings.list_by_investigation(inv.id, types={FindingType.DOMAIN})
        assert {f.normalized_value for f in domains} == {"example.com", "example.org"}
        confident = await uow.findings.list_by_investigation(inv.id, min_confidence=0.7)
        assert {f.id for f in confident} == {findings[0].id, findings[2].id}
        page = await uow.findings.list_by_investigation(inv.id, limit=1, offset=1)
        assert [f.id for f in page] == [findings[1].id]
        assert await uow.findings.count_by_investigation(inv.id) == 3
        assert await uow.findings.get(findings[0].id) is not None
        assert await uow.findings.get(uuid4()) is None
        other = await uow.findings.list_by_investigation(uuid4())
        assert other == []


async def test_finding_requires_known_source_foreign_key(
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    async with uow_factory() as uow:
        inv = await _seed(uow)
        evidence = make_evidence(inv.id)
        await uow.evidence.add(evidence)
        with pytest.raises(IntegrityError):
            await uow.findings.add_many([make_finding(inv.id, evidence=evidence, source="nope")])


async def test_source_upsert_updates_existing(uow_factory: Callable[[], UnitOfWork]) -> None:
    async with uow_factory() as uow:
        await uow.sources.upsert_many([make_source("dns")])
        renamed = make_source("dns").model_copy(update={"display_name": "Renamed"})
        await uow.sources.upsert_many([renamed])
        await uow.commit()
    async with uow_factory() as uow:
        assert (await uow.sources.get("dns")) == renamed
        assert await uow.sources.existing_names({"dns", "x"}) == {"dns"}
        assert await uow.sources.existing_names(set()) == set()
        assert len(await uow.sources.list_all()) == 1


async def test_entities_relationships_scores_reports_outbox(
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    async with uow_factory() as uow:
        inv = await _seed(uow)
        domain = Entity(
            investigation_id=inv.id,
            type=EntityType.DOMAIN,
            normalized_value="example.com",
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
        ip = Entity(
            investigation_id=inv.id,
            type=EntityType.IP_ADDRESS,
            normalized_value="192.0.2.1",
            created_at=FIXED_NOW,
            updated_at=FIXED_NOW,
        )
        await uow.entities.add(domain)
        await uow.entities.add(ip)
        rel = Relationship(
            investigation_id=inv.id,
            source_entity_id=domain.id,
            target_entity_id=ip.id,
            type=RelationType.RESOLVES_TO,
            confidence=0.9,
            provenance_kind=ProvenanceKind.DERIVED,
            created_at=FIXED_NOW,
        )
        await uow.relationships.add(rel)
        low = Score(investigation_id=inv.id, exposure=10, confidence=0.5, created_at=FIXED_NOW)
        high = Score(
            investigation_id=inv.id,
            exposure=55,
            confidence=0.6,
            created_at=FIXED_NOW + timedelta(seconds=1),
        )
        await uow.scores.add(low)
        await uow.scores.add(high)
        report = Report(investigation_id=inv.id, format="json", title="R", created_at=FIXED_NOW)
        await uow.reports.add(report)
        event = OutboxEvent(
            operation="upsert_entity",
            aggregate_type="entity",
            aggregate_id=domain.id,
            investigation_id=inv.id,
            created_at=FIXED_NOW,
        )
        await uow.outbox.add(event)
        await uow.commit()
    async with uow_factory() as uow:
        assert len(await uow.entities.list_by_investigation(inv.id)) == 2
        only_ips = await uow.entities.list_by_investigation(inv.id, types={EntityType.IP_ADDRESS})
        assert [e.id for e in only_ips] == [ip.id]
        assert await uow.entities.get(domain.id) == domain
        assert await uow.relationships.get(rel.id) == rel
        assert (await uow.relationships.list_by_investigation(inv.id)) == [rel]
        latest = await uow.scores.latest(inv.id)
        assert latest is not None
        assert latest.id == high.id
        assert len(await uow.scores.list_by_investigation(inv.id)) == 2
        assert await uow.reports.get(report.id) == report
        assert (await uow.reports.list_by_investigation(inv.id)) == [report]
        pending = await uow.outbox.list_pending()
        assert len(pending) == 1
        assert pending[0].id is not None
        await uow.outbox.mark_processed(pending[0].id, at=FIXED_NOW)
        assert await uow.outbox.list_pending() == []
        assert len(await uow.outbox.list_by_investigation(inv.id)) == 1


async def test_score_and_confidence_check_constraints(
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    async with uow_factory() as uow:
        inv = await _seed(uow)
        bad = Score.model_construct(
            id=uuid4(),
            investigation_id=inv.id,
            exposure=150.0,
            confidence=0.5,
            breakdown={},
            config_sha256=None,
            created_at=FIXED_NOW,
        )
        with pytest.raises(IntegrityError):
            await uow.scores.add(bad)


async def test_investigation_list_is_newest_first(uow_factory: Callable[[], UnitOfWork]) -> None:
    async with uow_factory() as uow:
        old = Investigation(name="old", created_at=FIXED_NOW, updated_at=FIXED_NOW)
        new = Investigation(
            name="new",
            created_at=FIXED_NOW + timedelta(days=1),
            updated_at=FIXED_NOW + timedelta(days=1),
        )
        await uow.investigations.add(old)
        await uow.investigations.add(new)
        listed = await uow.investigations.list_all()
        assert [i.name for i in listed] == ["new", "old"]
