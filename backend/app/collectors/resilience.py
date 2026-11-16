"""Resilience policy for collectors (SPECS.md §21) — INTERFACE ONLY in Phase 1.

Execution order for one (collector, target) call, implemented in Phase 3
(docs/phases/phase-03.md) by `DefaultResilientExecutor`:

    circuit_breaker.before_call()          -> CircuitOpenError  => CIRCUIT_OPEN, no retry
    for attempt in 1..retry.max_attempts:
        await rate_limiter.acquire(key)    -> waits; never raises unless cancelled
        async with asyncio.timeout(timeout_seconds):
            findings = await collector.collect(target)
        on success: circuit_breaker.record_success(); validate_output(); return SUCCESS
        on TransientCollectorError / timeout:
            circuit_breaker.record_failure(); sleep(compute_backoff(attempt, retry))
            (RateLimitedError.retry_after, when given, overrides the computed delay)
        on PermanentCollectorError / CollectorContractError: record_failure(); ERROR
    after the last attempt: TIMEOUT or ERROR (the last error kind wins)

A failing collector never raises out of the executor: it always returns a
CollectorOutcome, so one failure cannot stop the investigation.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol, runtime_checkable
from uuid import UUID

from app.collectors.base import Collector
from app.core.config import CircuitBreakerConfig, CollectorConfig, RetryConfig
from app.domain.enums import CollectorRunStatus
from app.domain.finding import Finding
from app.domain.rate_limit import RateLimit
from app.domain.target import Target


@dataclass(frozen=True, slots=True)
class ResiliencePolicy:
    """Everything the executor needs, resolved from collectors.yaml + class defaults."""

    timeout_seconds: float
    retry: RetryConfig
    circuit_breaker: CircuitBreakerConfig
    rate_limit: RateLimit

    @classmethod
    def for_collector(cls, collector: Collector) -> ResiliencePolicy:
        return cls.from_config(collector.config, default_rate_limit=collector.rate_limit)

    @classmethod
    def from_config(
        cls, config: CollectorConfig, default_rate_limit: RateLimit
    ) -> ResiliencePolicy:
        return cls(
            timeout_seconds=config.timeout_seconds,
            retry=config.retry,
            circuit_breaker=config.circuit_breaker,
            rate_limit=config.rate_limit or default_rate_limit,
        )


def compute_backoff(
    attempt: int,
    retry: RetryConfig,
    rng: Callable[[], float] = random.random,
) -> float:
    """Exponential backoff with "equal jitter", capped at backoff_max_seconds.

    attempt is 1-based (the delay *after* the attempt-th failure).
        base   = min(max, base_seconds * 2 ** (attempt - 1))
        delay  = base * (1 - jitter) + base * jitter * rng()
    jitter=0 gives the deterministic exponential sequence.
    """
    if attempt < 1:
        raise ValueError("attempt is 1-based")
    ceiling = min(retry.backoff_max_seconds, retry.backoff_base_seconds * 2.0 ** (attempt - 1))
    return ceiling * (1 - retry.jitter) + ceiling * retry.jitter * rng()


class CircuitState(StrEnum):
    CLOSED = "closed"  # calls flow; failures are counted
    OPEN = "open"  # calls rejected until recovery_timeout_seconds elapse
    HALF_OPEN = "half_open"  # up to half_open_max_calls trial calls allowed


@runtime_checkable
class RateLimiter(Protocol):
    """Token bucket keyed by collector name (shared across workers when Redis-backed).

    Phase 3 provides InMemoryRateLimiter (tests, inline mode) and RedisRateLimiter.
    """

    async def acquire(self, key: str, limit: RateLimit) -> None:
        """Wait until a token is available for `key`."""
        ...


@runtime_checkable
class CircuitBreaker(Protocol):
    """Per-collector breaker: CLOSED -> OPEN after `failure_threshold` consecutive
    failures; OPEN -> HALF_OPEN after `recovery_timeout_seconds`; HALF_OPEN -> CLOSED on
    success or back to OPEN on failure."""

    @property
    def state(self) -> CircuitState: ...

    async def before_call(self) -> None:
        """Raise CircuitOpenError if the call must not be attempted."""
        ...

    async def record_success(self) -> None: ...

    async def record_failure(self) -> None: ...


@dataclass(slots=True)
class CollectorOutcome:
    """Result of one (collector, target) execution. Persisted as a CollectorRun (Phase 2)."""

    collector: str
    target_id: UUID
    status: CollectorRunStatus
    findings: list[Finding] = field(default_factory=list)
    attempts: int = 0
    duration_seconds: float = 0.0
    error: str | None = None  # short, sanitized message; never secrets or raw payloads


@runtime_checkable
class ResilientExecutor(Protocol):
    """Runs a collector under its ResiliencePolicy. Must never raise for collector errors."""

    async def run(self, collector: Collector, target: Target) -> CollectorOutcome: ...
