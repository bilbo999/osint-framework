"""FindingPersister: the only writer of collector output (CLAUDE.md rule 2).

Everything happens in ONE transaction: if any check fails nothing is stored.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from typing import Any

from app.collectors.resilience import CollectorOutcome
from app.core.config import EvidenceSection
from app.db.uow import UnitOfWork
from app.domain.enums import InvestigationStatus
from app.domain.evidence import Evidence
from app.domain.records import CollectorRun
from app.domain.source import Source
from app.services.errors import (
    InvestigationClosedError,
    InvestigationNotFoundError,
    MissingEvidenceError,
    MissingSourceError,
    PersistenceError,
    TargetNotFoundError,
)

#: Collector error messages are already sanitized; this only bounds the stored size.
MAX_ERROR_CHARS = 2000


def _utc_now() -> datetime:
    return datetime.now(UTC)


def _truncate_utf8(text: str, max_bytes: int) -> str:
    return text.encode("utf-8")[:max_bytes].decode("utf-8", errors="ignore")


class FindingPersister:
    def __init__(
        self,
        uow_factory: Callable[[], UnitOfWork],
        evidence_cfg: EvidenceSection,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._uow_factory = uow_factory
        self._evidence_cfg = evidence_cfg
        self._clock = clock

    async def persist(self, outcome: CollectorOutcome, sources: Sequence[Source]) -> int:
        """Upsert sources, insert evidence (dedupe by id, truncated to max_content_bytes with
        metadata 'truncated': true and the sha256 of the original), insert findings and the
        collector_run. Returns the number of findings stored."""
        now = self._clock()
        async with self._uow_factory() as uow:
            target = await uow.targets.get(outcome.target_id)
            if target is None:
                raise TargetNotFoundError(outcome.target_id)
            investigation = await uow.investigations.get(target.investigation_id)
            if investigation is None:
                raise InvestigationNotFoundError(target.investigation_id)
            if investigation.status is InvestigationStatus.CLOSED:
                raise InvestigationClosedError(investigation.id)

            for finding in outcome.findings:
                if finding.investigation_id != investigation.id:
                    raise PersistenceError("finding belongs to a different investigation")

            # Evidence attached to findings, deduplicated by id (first one wins).
            attached: dict[Any, Evidence] = {}
            for finding in outcome.findings:
                if finding.evidence is not None:
                    attached.setdefault(finding.evidence.id, finding.evidence)
            referenced = {f.evidence_id for f in outcome.findings if f.evidence_id is not None}
            unattached = referenced - attached.keys()
            stored_ids = await uow.evidence.existing_ids(unattached | attached.keys())
            missing = unattached - stored_ids
            if missing:
                raise MissingEvidenceError(
                    f"findings reference unknown evidence: {sorted(str(m) for m in missing)}"
                )

            # Every source referenced must be provided or already known.
            needed = {f.source for f in outcome.findings} | {e.source for e in attached.values()}
            provided = {s.name for s in sources}
            unknown = needed - provided - await uow.sources.existing_names(needed - provided)
            if unknown:
                raise MissingSourceError(f"unknown sources: {sorted(unknown)}")

            await uow.sources.upsert_many(sources)
            for evidence in attached.values():
                if evidence.id not in stored_ids:
                    await self._store_evidence(uow, evidence, now)
            await uow.findings.add_many(outcome.findings, created_at=now)
            await uow.collector_runs.add(
                CollectorRun(
                    investigation_id=investigation.id,
                    target_id=outcome.target_id,
                    collector=outcome.collector,
                    status=outcome.status,
                    attempts=outcome.attempts,
                    duration_seconds=outcome.duration_seconds,
                    findings_count=len(outcome.findings),
                    error=outcome.error[:MAX_ERROR_CHARS] if outcome.error else None,
                    created_at=now,
                )
            )
            await uow.commit()
        return len(outcome.findings)

    async def _store_evidence(self, uow: UnitOfWork, evidence: Evidence, now: datetime) -> None:
        limit = self._evidence_cfg.max_content_bytes
        original_size = len(evidence.content.encode("utf-8"))
        if original_size <= limit:
            await uow.evidence.add(evidence, created_at=now)
            return
        await uow.evidence.add(
            evidence,
            content=_truncate_utf8(evidence.content, limit),
            metadata={
                "truncated": True,
                "original_size_bytes": original_size,
                "original_sha256": evidence.sha256,
            },
            created_at=now,
        )
