"""ORM row <-> domain object conversions. The only place that knows both representations.

`*_to_row` builds a detached ORM object; `*_to_domain` returns an immutable domain value, so
ORM instances never leave `app/repositories`.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.domain.evidence import Evidence
from app.domain.finding import Finding, NormalizationStep, RelationHint
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
from app.domain.source import Source
from app.domain.target import Target, TargetSeeds
from app.models import (
    AuditRow,
    CollectorRunRow,
    EntityRow,
    EvidenceRow,
    FindingRow,
    InvestigationRow,
    OutboxRow,
    RelationshipRow,
    ReportRow,
    ScoreRow,
    SourceRow,
    TargetRow,
)


def _now() -> datetime:
    return datetime.now(UTC)


# ------------------------------------------------------------------ investigation
def investigation_to_row(inv: Investigation) -> InvestigationRow:
    return InvestigationRow(**inv.model_dump())


def investigation_to_domain(row: InvestigationRow) -> Investigation:
    return Investigation(
        id=row.id,
        name=row.name,
        description=row.description,
        status=row.status,
        is_synthetic=row.is_synthetic,
        owner_id=row.owner_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
        closed_at=row.closed_at,
    )


# ------------------------------------------------------------------ target
def target_to_row(target: Target) -> TargetRow:
    return TargetRow(
        id=target.id,
        investigation_id=target.investigation_id,
        type=target.type,
        value=target.value,
        seeds=target.seeds.model_dump(mode="json") if target.seeds else None,
        parent_target_id=target.parent_target_id,
        pivot_depth=target.pivot_depth,
        created_at=target.created_at,
    )


def target_to_domain(row: TargetRow) -> Target:
    return Target(
        id=row.id,
        investigation_id=row.investigation_id,
        type=row.type,
        value=row.value,
        seeds=TargetSeeds.model_validate(row.seeds) if row.seeds else None,
        parent_target_id=row.parent_target_id,
        pivot_depth=row.pivot_depth,
        created_at=row.created_at,
    )


# ------------------------------------------------------------------ source
def source_to_row(source: Source) -> SourceRow:
    return SourceRow(**source.model_dump())


def source_to_domain(row: SourceRow) -> Source:
    return Source(
        name=row.name,
        display_name=row.display_name,
        kind=row.kind,
        homepage_url=row.homepage_url,
        terms_url=row.terms_url,
        requires_api_key=row.requires_api_key,
        is_synthetic=row.is_synthetic,
    )


# ------------------------------------------------------------------ evidence
def evidence_to_row(
    evidence: Evidence,
    *,
    content: str | None = None,
    metadata: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> EvidenceRow:
    """`content` overrides the stored text (truncation); `sha256` always stays the original's."""
    return EvidenceRow(
        id=evidence.id,
        investigation_id=evidence.investigation_id,
        kind=evidence.kind,
        source=evidence.source,
        collector=evidence.collector,
        source_url=evidence.source_url,
        request_summary=evidence.request_summary,
        retrieved_at=evidence.retrieved_at,
        content_type=evidence.content_type,
        content=evidence.content if content is None else content,
        sha256=evidence.sha256,
        is_synthetic=evidence.is_synthetic,
        meta=dict(metadata or {}),
        created_at=created_at or _now(),
    )


def evidence_to_domain(row: EvidenceRow) -> Evidence:
    fields: dict[str, Any] = {
        "id": row.id,
        "investigation_id": row.investigation_id,
        "kind": row.kind,
        "source": row.source,
        "collector": row.collector,
        "source_url": row.source_url,
        "request_summary": row.request_summary,
        "retrieved_at": row.retrieved_at,
        "content_type": row.content_type,
        "content": row.content,
        "sha256": row.sha256,
        "is_synthetic": row.is_synthetic,
    }
    if row.meta.get("truncated"):
        # Stored content is a prefix of the original, so its hash cannot match `sha256`
        # (which is the original's). Skip the integrity validator on purpose.
        return Evidence.model_construct(**fields)
    return Evidence(**fields)


def evidence_is_truncated(row: EvidenceRow) -> bool:
    return bool(row.meta.get("truncated"))


# ------------------------------------------------------------------ finding
def finding_to_row(finding: Finding, *, created_at: datetime | None = None) -> FindingRow:
    return FindingRow(
        id=finding.id,
        investigation_id=finding.investigation_id,
        target_id=finding.target_id,
        evidence_id=finding.evidence_id,
        type=finding.type,
        value=finding.value,
        normalized_value=finding.normalized_value,
        raw_value=finding.raw_value,
        normalization_steps=[s.model_dump(mode="json") for s in finding.normalization_steps],
        source=finding.source,
        source_url=finding.source_url,
        timestamp=finding.timestamp,
        confidence=finding.confidence,
        collector=finding.collector,
        provenance_kind=finding.provenance_kind,
        derived_from=[str(u) for u in finding.derived_from],
        relation_hint=(
            finding.relation_hint.model_dump(mode="json") if finding.relation_hint else None
        ),
        is_synthetic=finding.is_synthetic,
        meta=dict(finding.metadata),
        created_at=created_at or _now(),
    )


def finding_to_domain(row: FindingRow) -> Finding:
    return Finding(
        id=row.id,
        type=row.type,
        value=row.value,
        normalized_value=row.normalized_value,
        raw_value=row.raw_value,
        normalization_steps=[NormalizationStep.model_validate(s) for s in row.normalization_steps],
        source=row.source,
        source_url=row.source_url,
        timestamp=row.timestamp,
        confidence=row.confidence,
        collector=row.collector,
        investigation_id=row.investigation_id,
        target_id=row.target_id,
        evidence_id=row.evidence_id,
        provenance_kind=row.provenance_kind,
        derived_from=[UUID(u) for u in row.derived_from],
        relation_hint=RelationHint.model_validate(row.relation_hint) if row.relation_hint else None,
        is_synthetic=row.is_synthetic,
        metadata=row.meta,
    )


# ------------------------------------------------------------------ collector run
def collector_run_to_row(run: CollectorRun) -> CollectorRunRow:
    return CollectorRunRow(**run.model_dump())


def collector_run_to_domain(row: CollectorRunRow) -> CollectorRun:
    return CollectorRun(
        id=row.id,
        investigation_id=row.investigation_id,
        target_id=row.target_id,
        collector=row.collector,
        status=row.status,
        attempts=row.attempts,
        duration_seconds=row.duration_seconds,
        findings_count=row.findings_count,
        error=row.error,
        created_at=row.created_at,
    )


# ------------------------------------------------------------------ entity / relationship
def entity_to_row(entity: Entity) -> EntityRow:
    return EntityRow(
        id=entity.id,
        investigation_id=entity.investigation_id,
        type=entity.type,
        normalized_value=entity.normalized_value,
        display_name=entity.display_name,
        confidence=entity.confidence,
        attributes=dict(entity.attributes),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def entity_to_domain(row: EntityRow) -> Entity:
    return Entity(
        id=row.id,
        investigation_id=row.investigation_id,
        type=row.type,
        normalized_value=row.normalized_value,
        display_name=row.display_name,
        confidence=row.confidence,
        attributes=row.attributes,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def relationship_to_row(rel: Relationship) -> RelationshipRow:
    return RelationshipRow(
        id=rel.id,
        investigation_id=rel.investigation_id,
        source_entity_id=rel.source_entity_id,
        target_entity_id=rel.target_entity_id,
        type=rel.type,
        confidence=rel.confidence,
        provenance_kind=rel.provenance_kind,
        finding_ids=[str(u) for u in rel.finding_ids],
        created_at=rel.created_at,
    )


def relationship_to_domain(row: RelationshipRow) -> Relationship:
    return Relationship(
        id=row.id,
        investigation_id=row.investigation_id,
        source_entity_id=row.source_entity_id,
        target_entity_id=row.target_entity_id,
        type=row.type,
        confidence=row.confidence,
        provenance_kind=row.provenance_kind,
        finding_ids=[UUID(u) for u in row.finding_ids],
        created_at=row.created_at,
    )


# ------------------------------------------------------------------ score / report
def score_to_row(score: Score) -> ScoreRow:
    return ScoreRow(
        id=score.id,
        investigation_id=score.investigation_id,
        exposure=score.exposure,
        confidence=score.confidence,
        breakdown=dict(score.breakdown),
        config_sha256=score.config_sha256,
        created_at=score.created_at,
    )


def score_to_domain(row: ScoreRow) -> Score:
    return Score(
        id=row.id,
        investigation_id=row.investigation_id,
        exposure=row.exposure,
        confidence=row.confidence,
        breakdown=row.breakdown,
        config_sha256=row.config_sha256,
        created_at=row.created_at,
    )


def report_to_row(report: Report) -> ReportRow:
    return ReportRow(**report.model_dump())


def report_to_domain(row: ReportRow) -> Report:
    return Report(
        id=row.id,
        investigation_id=row.investigation_id,
        format=row.format,
        title=row.title,
        file_path=row.file_path,
        sha256=row.sha256,
        is_synthetic=row.is_synthetic,
        created_at=row.created_at,
    )


# ------------------------------------------------------------------ audit / outbox
def audit_to_row(event: AuditEvent) -> AuditRow:
    return AuditRow(**event.model_dump(mode="python"))


def audit_to_domain(row: AuditRow) -> AuditEvent:
    return AuditEvent(
        id=row.id,
        investigation_id=row.investigation_id,
        actor=row.actor,
        action=row.action,
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        details=row.details,
        created_at=row.created_at,
    )


def outbox_to_row(event: OutboxEvent) -> OutboxRow:
    values = event.model_dump(mode="python")
    if values["id"] is None:
        del values["id"]  # let the database assign it
    return OutboxRow(**values)


def outbox_to_domain(row: OutboxRow) -> OutboxEvent:
    return OutboxEvent(
        id=row.id,
        operation=row.operation,
        aggregate_type=row.aggregate_type,
        aggregate_id=row.aggregate_id,
        investigation_id=row.investigation_id,
        payload=row.payload,
        created_at=row.created_at,
        processed_at=row.processed_at,
        attempts=row.attempts,
        last_error=row.last_error,
    )
