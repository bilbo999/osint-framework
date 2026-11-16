"""Collector inside a nested sub-package."""

from typing import ClassVar

from app.collectors.base import Collector
from app.domain import Finding, FindingType, RateLimit, Source, SourceKind, Target, TargetType


class BetaCollector(Collector):
    name: ClassVar[str] = "beta"
    description: ClassVar[str] = "Beta test collector."
    supported_targets: ClassVar[frozenset[TargetType]] = frozenset(
        {TargetType.DOMAIN, TargetType.URL}
    )
    source: ClassVar[Source] = Source(name="beta_src", display_name="Beta", kind=SourceKind.DNS)
    rate_limit: ClassVar[RateLimit] = RateLimit(requests=5, per_seconds=1)
    data_types: ClassVar[frozenset[FindingType]] = frozenset({FindingType.IP_ADDRESS})

    async def collect(self, target: Target) -> list[Finding]:
        return []
