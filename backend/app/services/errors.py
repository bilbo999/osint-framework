"""Service-layer errors (mapped to HTTP statuses by the API in Phase 8)."""

from __future__ import annotations

from uuid import UUID


class ServiceError(Exception):
    """Base class for expected, user-facing service failures."""


class InvestigationNotFoundError(ServiceError):
    def __init__(self, investigation_id: UUID) -> None:
        super().__init__(f"investigation {investigation_id} not found")
        self.investigation_id = investigation_id


class InvestigationClosedError(ServiceError):
    """Raised on any write to a CLOSED investigation (read-only until reopened)."""

    def __init__(self, investigation_id: UUID) -> None:
        super().__init__(f"investigation {investigation_id} is closed (read-only)")
        self.investigation_id = investigation_id


class PersistenceError(ServiceError):
    """Collector output cannot be persisted consistently (nothing is written)."""


class TargetNotFoundError(PersistenceError):
    def __init__(self, target_id: UUID) -> None:
        super().__init__(f"target {target_id} not found")
        self.target_id = target_id


class MissingEvidenceError(PersistenceError):
    """A finding references evidence that is neither attached nor already stored."""


class MissingSourceError(PersistenceError):
    """A finding/evidence references a source that was not provided nor stored."""
