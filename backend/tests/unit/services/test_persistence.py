"""FindingPersister: dedupe, truncation, collector runs, all-or-nothing writes."""

from __future__ import annotations

from collections.abc import Callable
from uuid import UUID, uuid4

import pytest

from app.collectors.resilience import CollectorOutcome
from app.core.config import AppConfig, EvidenceSection
from app.db.uow import UnitOfWork
from app.domain import Target, TargetType
from app.domain.enums import CollectorRunStatus
from app.schemas.investigation import TargetCreate
from app.services.errors import (
    InvestigationClosedError,
    MissingEvidenceError,
    MissingSourceError,
    PersistenceError,
    TargetNotFoundError,
)
from app.services.investigations import InvestigationService
from app.services.persistence import FindingPersister
from tests.conftest import FIXED_NOW
from tests.fixtures.builders import make_evidence, make_finding, make_source


async def _setup(service: InvestigationService) -> tuple[UUID, Target]:
    inv = await service.create("case", None)
    target = await service.add_target(
        inv.id, TargetCreate(type=TargetType.DOMAIN, value="example.com")
    )
    return inv.id, target


def _outcome(target: Target, findings: list, **kw: object) -> CollectorOutcome:  # type: ignore[type-arg]
    return CollectorOutcome(
        collector="dns_records",
        target_id=target.id,
        status=CollectorRunStatus.SUCCESS,
        findings=findings,
        attempts=1,
        duration_seconds=0.25,
        **kw,  # type: ignore[arg-type]
    )


async def test_persist_stores_findings_evidence_sources_and_run(
    persister: FindingPersister,
    investigation_service: InvestigationService,
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    inv_id, target = await _setup(investigation_service)
    evidence = make_evidence(inv_id)
    findings = [
        make_finding(inv_id, evidence=evidence, target_id=target.id),
        make_finding(
            inv_id,
            evidence=evidence,
            target_id=target.id,
            value="192.0.2.2",
            normalized_value="192.0.2.2",
            normalization_steps=[],
        ),
    ]
    stored = await persister.persist(_outcome(target, findings), [make_source("dns")])
    assert stored == 2
    async with uow_factory() as uow:
        got = await uow.findings.list_by_investigation(inv_id)
        assert {f.id for f in got} == {f.id for f in findings}
        assert all(f.evidence_id == evidence.id for f in got)
        assert await uow.evidence.get(evidence.id) == evidence
        assert await uow.sources.get("dns") is not None
        (run,) = await uow.collector_runs.list_by_investigation(inv_id)
        assert run.status is CollectorRunStatus.SUCCESS
        assert run.findings_count == 2
        assert run.duration_seconds == 0.25
        assert run.attempts == 1
        assert run.target_id == target.id
        assert run.error is None


async def test_persist_deduplicates_shared_and_already_stored_evidence(
    persister: FindingPersister,
    investigation_service: InvestigationService,
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    inv_id, target = await _setup(investigation_service)
    evidence = make_evidence(inv_id)
    # Same evidence id attached through two distinct (equal) objects.
    twin = evidence.model_copy()
    first = make_finding(inv_id, evidence=evidence)
    second = make_finding(inv_id, evidence=twin, value="192.0.2.3", normalized_value="192.0.2.3")
    await persister.persist(_outcome(target, [first, second]), [make_source("dns")])
    # A later run references the evidence by id only (no attached object).
    third = make_finding(inv_id, evidence=evidence, value="192.0.2.4", normalized_value="192.0.2.4")
    detached = third.model_copy(update={"evidence": None})
    await persister.persist(_outcome(target, [detached]), [make_source("dns")])
    async with uow_factory() as uow:
        assert len(await uow.evidence.list_by_investigation(inv_id)) == 1
        assert await uow.findings.count_by_investigation(inv_id) == 3
        assert len(await uow.collector_runs.list_by_investigation(inv_id)) == 2


async def test_persist_truncates_large_evidence_and_flags_it(
    uow_factory: Callable[[], UnitOfWork],
    investigation_service: InvestigationService,
) -> None:
    persister = FindingPersister(
        uow_factory, EvidenceSection(max_content_bytes=10, store_raw_content=True)
    )
    inv_id, target = await _setup(investigation_service)
    original = "é" * 20  # 40 bytes in UTF-8
    evidence = make_evidence(inv_id, content=original)
    finding = make_finding(inv_id, evidence=evidence)
    await persister.persist(_outcome(target, [finding]), [make_source("dns")])
    async with uow_factory() as uow:
        stored = await uow.evidence.get(evidence.id)
        meta = await uow.evidence.get_metadata(evidence.id)
    assert stored is not None
    assert meta is not None
    assert len(stored.content.encode("utf-8")) <= 10
    assert original.startswith(stored.content)
    assert stored.sha256 == evidence.sha256  # sha256 of the original
    assert meta["truncated"] is True
    assert meta["original_size_bytes"] == 40


async def test_persist_does_not_truncate_within_limit(
    persister: FindingPersister,
    investigation_service: InvestigationService,
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    inv_id, target = await _setup(investigation_service)
    evidence = make_evidence(inv_id)
    await persister.persist(
        _outcome(target, [make_finding(inv_id, evidence=evidence)]), [make_source("dns")]
    )
    async with uow_factory() as uow:
        assert await uow.evidence.get_metadata(evidence.id) == {}


async def test_persist_failed_run_without_findings_records_error(
    persister: FindingPersister,
    investigation_service: InvestigationService,
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    inv_id, target = await _setup(investigation_service)
    outcome = CollectorOutcome(
        collector="dns_records",
        target_id=target.id,
        status=CollectorRunStatus.TIMEOUT,
        attempts=3,
        duration_seconds=30.0,
        error="timed out after 10s",
    )
    assert await persister.persist(outcome, []) == 0
    async with uow_factory() as uow:
        (run,) = await uow.collector_runs.list_by_investigation(inv_id)
    assert run.status is CollectorRunStatus.TIMEOUT
    assert (run.attempts, run.duration_seconds, run.findings_count) == (3, 30.0, 0)
    assert run.error == "timed out after 10s"


async def test_persist_rejects_finding_with_unknown_evidence_and_writes_nothing(
    persister: FindingPersister,
    investigation_service: InvestigationService,
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    inv_id, target = await _setup(investigation_service)
    evidence = make_evidence(inv_id)
    good = make_finding(inv_id, evidence=evidence)
    orphan = make_finding(
        inv_id, evidence=make_evidence(inv_id), value="192.0.2.9", normalized_value="192.0.2.9"
    )
    orphan_detached = orphan.model_copy(update={"evidence": None})  # id kept, object dropped
    with pytest.raises(MissingEvidenceError):
        await persister.persist(_outcome(target, [good, orphan_detached]), [make_source("dns")])
    async with uow_factory() as uow:
        assert await uow.findings.count_by_investigation(inv_id) == 0
        assert await uow.evidence.list_by_investigation(inv_id) == []
        assert await uow.collector_runs.list_by_investigation(inv_id) == []


async def test_persist_rejects_unknown_source(
    persister: FindingPersister, investigation_service: InvestigationService
) -> None:
    inv_id, target = await _setup(investigation_service)
    finding = make_finding(inv_id, evidence=make_evidence(inv_id))
    with pytest.raises(MissingSourceError):
        await persister.persist(_outcome(target, [finding]), [])


async def test_persist_rejects_unknown_target_and_foreign_findings(
    persister: FindingPersister, investigation_service: InvestigationService
) -> None:
    _inv_id, target = await _setup(investigation_service)
    ghost = CollectorOutcome(collector="x1", target_id=uuid4(), status=CollectorRunStatus.SKIPPED)
    with pytest.raises(TargetNotFoundError):
        await persister.persist(ghost, [])
    other = uuid4()
    foreign = make_finding(other, evidence=make_evidence(other))
    with pytest.raises(PersistenceError, match="different investigation"):
        await persister.persist(_outcome(target, [foreign]), [make_source("dns")])


async def test_persist_refuses_closed_investigation(
    persister: FindingPersister, investigation_service: InvestigationService
) -> None:
    inv_id, target = await _setup(investigation_service)
    await investigation_service.close(inv_id)
    finding = make_finding(inv_id, evidence=make_evidence(inv_id))
    with pytest.raises(InvestigationClosedError):
        await persister.persist(_outcome(target, [finding]), [make_source("dns")])


def test_clock_default_is_aware(app_config: AppConfig) -> None:
    assert FIXED_NOW.tzinfo is not None
