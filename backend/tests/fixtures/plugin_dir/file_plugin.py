"""Stand-alone plugin file loaded by path (like the repo-level collectors/ directory)."""

from typing import ClassVar

from app.collectors.base import Collector
from app.domain import Finding, FindingType, RateLimit, Source, SourceKind, Target, TargetType


class FilePluginCollector(Collector):
    name: ClassVar[str] = "file_plugin"
    description: ClassVar[str] = "Loaded from a plugin directory."
    supported_targets: ClassVar[frozenset[TargetType]] = frozenset({TargetType.USERNAME})
    source: ClassVar[Source] = Source(
        name="file_src", display_name="File", kind=SourceKind.HTTP_API
    )
    rate_limit: ClassVar[RateLimit] = RateLimit(requests=1, per_seconds=2)
    data_types: ClassVar[frozenset[FindingType]] = frozenset({FindingType.ACCOUNT_PRESENCE})

    async def collect(self, target: Target) -> list[Finding]:
        return []
