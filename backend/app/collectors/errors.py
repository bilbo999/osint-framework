"""Exceptions raised by collectors and the resilience layer.

Mapping to CollectorRunStatus (Phase 3 executor):
    CollectorTimeoutError    -> TIMEOUT
    RateLimitedError         -> RATE_LIMITED   (retryable after `retry_after`)
    CircuitOpenError         -> CIRCUIT_OPEN   (not retried)
    TransientCollectorError  -> retried, then ERROR
    PermanentCollectorError  -> ERROR          (not retried)
    MissingApiKeyError       -> SKIPPED
    CollectorContractError   -> ERROR          (bug in the collector; never retried)
"""

from __future__ import annotations


class CollectorError(Exception):
    """Base class for every collector-related failure."""


class TransientCollectorError(CollectorError):
    """Temporary failure (network glitch, 5xx). Safe to retry."""


class PermanentCollectorError(CollectorError):
    """Failure that will not go away by retrying (4xx, bad input)."""


class CollectorTimeoutError(TransientCollectorError):
    """The collector exceeded its configured timeout."""


class RateLimitedError(TransientCollectorError):
    """The source (or our own limiter) refused the call for now."""

    def __init__(self, message: str = "rate limited", retry_after: float | None = None) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class CircuitOpenError(CollectorError):
    """The circuit breaker for this collector is open; the call was not attempted."""


class MissingApiKeyError(CollectorError):
    """The collector requires an API key that is not configured."""


class CollectorContractError(CollectorError):
    """The collector returned output that violates the Collector contract."""
