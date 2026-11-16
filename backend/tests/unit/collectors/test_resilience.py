"""Resilience skeleton: policy resolution and backoff maths (executor arrives in Phase 3)."""

from uuid import uuid4

import pytest

from app.collectors.resilience import (
    CircuitBreaker,
    CircuitState,
    CollectorOutcome,
    RateLimiter,
    ResiliencePolicy,
    compute_backoff,
)
from app.core.config import CollectorConfig, RetryConfig
from app.domain import CollectorRunStatus, RateLimit
from tests.fixtures.fakes import EchoCollector

RETRY = RetryConfig(max_attempts=5, backoff_base_seconds=0.5, backoff_max_seconds=4, jitter=0.0)


def test_exponential_sequence_without_jitter() -> None:
    assert [compute_backoff(n, RETRY) for n in range(1, 6)] == [0.5, 1.0, 2.0, 4.0, 4.0]


def test_jitter_bounds() -> None:
    retry = RETRY.model_copy(update={"jitter": 0.5})
    assert compute_backoff(3, retry, rng=lambda: 0.0) == 1.0
    assert compute_backoff(3, retry, rng=lambda: 1.0) == 2.0


def test_attempt_is_one_based() -> None:
    with pytest.raises(ValueError, match="1-based"):
        compute_backoff(0, RETRY)


def test_policy_uses_class_rate_limit_by_default(collector_config: CollectorConfig) -> None:
    policy = ResiliencePolicy.for_collector(EchoCollector(collector_config))
    assert policy.rate_limit == EchoCollector.rate_limit
    assert policy.timeout_seconds == collector_config.timeout_seconds
    assert policy.retry == collector_config.retry


def test_policy_honours_config_override(collector_config: CollectorConfig) -> None:
    override = RateLimit(requests=1, per_seconds=5)
    config = collector_config.model_copy(update={"rate_limit": override})
    assert ResiliencePolicy.for_collector(EchoCollector(config)).rate_limit == override


def test_interfaces_are_runtime_checkable() -> None:
    class Limiter:
        async def acquire(self, key: str, limit: RateLimit) -> None:
            return None

    assert isinstance(Limiter(), RateLimiter)
    assert not isinstance(Limiter(), CircuitBreaker)
    assert {s.value for s in CircuitState} == {"closed", "open", "half_open"}


def test_outcome_defaults() -> None:
    outcome = CollectorOutcome(
        collector="echo", target_id=uuid4(), status=CollectorRunStatus.TIMEOUT
    )
    assert outcome.findings == []
    assert outcome.error is None
