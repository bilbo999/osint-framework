"""ORM models. Importing this package registers every table on `Base.metadata` (Alembic)."""

from app.models.audit import AuditRow
from app.models.collector_run import CollectorRunRow
from app.models.entity import EntityRow
from app.models.evidence import EvidenceRow
from app.models.finding import FindingRow
from app.models.investigation import InvestigationRow
from app.models.outbox import OutboxRow
from app.models.relationship import RelationshipRow
from app.models.report import ReportRow
from app.models.score import ScoreRow
from app.models.source import SourceRow
from app.models.target import TargetRow

__all__ = [
    "AuditRow",
    "CollectorRunRow",
    "EntityRow",
    "EvidenceRow",
    "FindingRow",
    "InvestigationRow",
    "OutboxRow",
    "RelationshipRow",
    "ReportRow",
    "ScoreRow",
    "SourceRow",
    "TargetRow",
]
