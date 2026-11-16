"""Implementation module of the package plugin."""

from typing import ClassVar

from app.collectors.base import Collector
from app.domain import Finding, FindingType, RateLimit, Source, SourceKind, Target, TargetType


class PackagePluginCollector(Collector):
    name: ClassVar[str] = "pkg_plugin"
    description: ClassVar[str] = "Package plugin."
    supported_targets: ClassVar[frozenset[TargetType]] = frozenset({TargetType.PHONE})
    source: ClassVar[Source] = Source(
        name="pkg_src", display_name="Pkg", kind=SourceKind.LOCAL_PARSER
    )
    rate_limit: ClassVar[RateLimit] = RateLimit(requests=1, per_seconds=1)
    data_types: ClassVar[frozenset[FindingType]] = frozenset({FindingType.PHONE_METADATA})

    async def collect(self, target: Target) -> list[Finding]:
        return []
