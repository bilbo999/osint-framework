"""Pure domain contracts (Pydantic, no I/O): Target, Finding, Evidence, Source and enums.

Every layer depends on this package; it depends on nothing else in the app.
"""

from app.domain.enums import (
    COLLECTOR_PROVENANCE,
    CollectorRunStatus,
    EntityType,
    FindingType,
    InvestigationStatus,
    ProvenanceKind,
    RelationType,
    Severity,
    TargetType,
)
from app.domain.evidence import Evidence, EvidenceKind
from app.domain.finding import Finding, NormalizationStep, RelationHint
from app.domain.rate_limit import RateLimit
from app.domain.source import Source, SourceKind
from app.domain.target import Target, TargetSeeds

__all__ = [
    "COLLECTOR_PROVENANCE",
    "CollectorRunStatus",
    "EntityType",
    "Evidence",
    "EvidenceKind",
    "Finding",
    "FindingType",
    "InvestigationStatus",
    "NormalizationStep",
    "ProvenanceKind",
    "RateLimit",
    "RelationHint",
    "RelationType",
    "Severity",
    "Source",
    "SourceKind",
    "Target",
    "TargetSeeds",
    "TargetType",
]
