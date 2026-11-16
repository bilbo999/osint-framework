"""RateLimit value object (declared by collectors, overridable in config/collectors.yaml)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, PositiveFloat, PositiveInt


class RateLimit(BaseModel):
    """At most `requests` calls every `per_seconds` seconds, with optional `burst`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    requests: PositiveInt
    per_seconds: PositiveFloat
    burst: PositiveInt | None = Field(
        default=None, description="Bucket size; defaults to requests."
    )

    @property
    def capacity(self) -> int:
        return self.burst or self.requests

    @property
    def refill_per_second(self) -> float:
        return self.requests / self.per_seconds
