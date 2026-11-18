"""Unit of Work: one transaction, all repositories sharing the same session."""

from __future__ import annotations

from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.audit import AuditRepository
from app.repositories.collector_runs import CollectorRunRepository
from app.repositories.entities import EntityRepository
from app.repositories.evidence import EvidenceRepository
from app.repositories.findings import FindingRepository
from app.repositories.investigations import InvestigationRepository
from app.repositories.outbox import OutboxRepository
from app.repositories.relationships import RelationshipRepository
from app.repositories.reports import ReportRepository
from app.repositories.scores import ScoreRepository
from app.repositories.sources import SourceRepository
from app.repositories.targets import TargetRepository


class UnitOfWork:
    """Usage::

        async with uow_factory() as uow:
            await uow.investigations.add(...)
            await uow.commit()

    Leaving the block without ``commit()`` (or on error) rolls the transaction back.
    """

    investigations: InvestigationRepository
    targets: TargetRepository
    findings: FindingRepository
    evidence: EvidenceRepository
    sources: SourceRepository
    entities: EntityRepository
    relationships: RelationshipRepository
    scores: ScoreRepository
    reports: ReportRepository
    collector_runs: CollectorRunRepository
    audit: AuditRepository
    outbox: OutboxRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> Self:
        session = self._session_factory()
        self._session = session
        self.investigations = InvestigationRepository(session)
        self.targets = TargetRepository(session)
        self.findings = FindingRepository(session)
        self.evidence = EvidenceRepository(session)
        self.sources = SourceRepository(session)
        self.entities = EntityRepository(session)
        self.relationships = RelationshipRepository(session)
        self.scores = ScoreRepository(session)
        self.reports = ReportRepository(session)
        self.collector_runs = CollectorRunRepository(session)
        self.audit = AuditRepository(session)
        self.outbox = OutboxRepository(session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._require_session()
        try:
            await session.rollback()  # no-op after a successful commit
        finally:
            await session.close()
            self._session = None

    async def commit(self) -> None:
        await self._require_session().commit()

    async def rollback(self) -> None:
        await self._require_session().rollback()

    def _require_session(self) -> AsyncSession:
        if self._session is None:
            raise RuntimeError("UnitOfWork used outside 'async with'")
        return self._session
