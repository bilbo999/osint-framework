"""ORM <-> domain round trips must preserve every field."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.domain import (
    EntityType,
    EvidenceKind,
    FindingType,
    ProvenanceKind,
    RelationHint,
    RelationType,
    Target,
    TargetSeeds,
    TargetType,
)
from app.domain.enums import CollectorRunStatus, InvestigationStatus
from app.domain.records import (
    AuditEvent,
    CollectorRun,
    Entity,
    Investigation,
    OutboxEvent,
    Relationship,
    Report,
    Score,
)
from app.repositories import mappers as m
from tests.conftest import FIXED_NOW
from tests.fixtures.builders import make_evidence, make_finding, make_source


def test_finding_round_trip_preserves_all_fields() -> None:
    inv = uuid4()
    evidence = make_evidence(inv)
    parent = make_finding(inv, evidence=evidence)
    finding = make_finding(
        inv,
        evidence=evidence,
        target_id=uuid4(),
        source_url="https://example.com/dns",
        relation_hint=RelationHint(
            subject_type=EntityType.DOMAIN,
            subject_value="example.com",
            relation=RelationType.RESOLVES_TO,
        ),
        raw_value={"nested": [1, 2.5, None, "x"], "ok": True},
        is_synthetic=True,
    )
    row = m.finding_to_row(finding)
    restored = m.finding_to_domain(row)
    assert restored.model_dump() == finding.model_dump()
    assert restored.raw_value == {"nested": [1, 2.5, None, "x"], "ok": True}
    assert restored.normalization_steps == finding.normalization_steps
    assert restored.relation_hint == finding.relation_hint
    assert restored.timestamp.tzinfo is UTC
    assert restored.timestamp == FIXED_NOW
    assert parent.id != finding.id


def test_finding_round_trip_inferred_with_derived_from_and_scalar_raw_value() -> None:
    inv = uuid4()
    base = make_finding(inv, evidence=make_evidence(inv))
    inferred = make_finding(
        inv,
        provenance_kind=ProvenanceKind.INFERRED,
        derived_from=[base.id],
        raw_value=None,
        type=FindingType.PERSON_NAME,
        value="A B",
        normalized_value="A B",
        normalization_steps=[],
    )
    restored = m.finding_to_domain(m.finding_to_row(inferred))
    assert restored.derived_from == [base.id]
    assert restored.raw_value is None
    assert restored.provenance_kind is ProvenanceKind.INFERRED
    assert restored.relation_hint is None


def test_evidence_round_trip() -> None:
    evidence = make_evidence(uuid4(), kind=EvidenceKind.SYNTHETIC, is_synthetic=True)
    restored = m.evidence_to_domain(m.evidence_to_row(evidence))
    assert restored == evidence


def test_truncated_evidence_keeps_original_hash() -> None:
    evidence = make_evidence(uuid4(), content="abcdef")
    row = m.evidence_to_row(evidence, content="abc", metadata={"truncated": True})
    restored = m.evidence_to_domain(row)
    assert restored.content == "abc"
    assert restored.sha256 == evidence.sha256
    assert m.evidence_is_truncated(row)


def test_source_round_trip() -> None:
    source = make_source("rdap_org", synthetic=True)
    assert m.source_to_domain(m.source_to_row(source)) == source


def test_target_round_trip_with_seeds_and_pivot() -> None:
    inv = uuid4()
    person = Target(
        investigation_id=inv,
        type=TargetType.PERSON,
        value="Alex Example",
        seeds=TargetSeeds(first_name="Alex", emails=["alex@example.com"]),
    )
    child = Target(
        investigation_id=inv,
        type=TargetType.EMAIL,
        value="alex@example.com",
        parent_target_id=person.id,
        pivot_depth=1,
    )
    assert m.target_to_domain(m.target_to_row(person)) == person
    assert m.target_to_domain(m.target_to_row(child)) == child


def test_remaining_records_round_trip() -> None:
    inv = uuid4()
    when = datetime(2026, 2, 1, 8, 30, tzinfo=UTC)
    investigation = Investigation(
        name="n",
        description="d",
        status=InvestigationStatus.CLOSED,
        is_synthetic=True,
        owner_id=uuid4(),
        created_at=when,
        updated_at=when,
        closed_at=when,
    )
    run = CollectorRun(
        investigation_id=inv,
        target_id=uuid4(),
        collector="dns_records",
        status=CollectorRunStatus.ERROR,
        attempts=3,
        duration_seconds=1.5,
        findings_count=0,
        error="timeout",
        created_at=when,
    )
    a, b = uuid4(), uuid4()
    entity = Entity(
        investigation_id=inv,
        type=EntityType.DOMAIN,
        normalized_value="example.com",
        display_name="Example",
        confidence=0.7,
        attributes={"k": [1, 2]},
        created_at=when,
        updated_at=when,
    )
    rel = Relationship(
        investigation_id=inv,
        source_entity_id=a,
        target_entity_id=b,
        type=RelationType.RESOLVES_TO,
        confidence=0.5,
        provenance_kind=ProvenanceKind.CORRELATED,
        finding_ids=[uuid4()],
        created_at=when,
    )
    score = Score(
        investigation_id=inv,
        exposure=42.5,
        confidence=0.8,
        breakdown={"identity": 14},
        config_sha256="a" * 64,
        created_at=when,
    )
    report = Report(
        investigation_id=inv, format="html", title="T", file_path="var/r.html", created_at=when
    )
    audit = AuditEvent(
        investigation_id=inv,
        actor="alice",
        action="x.y",
        entity_type="target",
        entity_id=uuid4(),
        details={"a": 1},
        created_at=when,
    )
    outbox = OutboxEvent(
        operation="upsert_entity",
        aggregate_type="entity",
        aggregate_id=uuid4(),
        investigation_id=inv,
        payload={"p": True},
        created_at=when,
    )
    assert m.investigation_to_domain(m.investigation_to_row(investigation)) == investigation
    assert m.collector_run_to_domain(m.collector_run_to_row(run)) == run
    assert m.entity_to_domain(m.entity_to_row(entity)) == entity
    assert m.relationship_to_domain(m.relationship_to_row(rel)) == rel
    assert m.score_to_domain(m.score_to_row(score)) == score
    assert m.report_to_domain(m.report_to_row(report)) == report
    assert m.audit_to_domain(m.audit_to_row(audit)) == audit
    assert m.outbox_to_domain(m.outbox_to_row(outbox)) == outbox
