"""Defines one concrete collector and one abstract intermediate base."""

from abc import abstractmethod
from typing import ClassVar

from app.collectors.base import Collector
from app.domain import Finding, FindingType, RateLimit, Source, SourceKind, Target, TargetType
from tests.fixtures.fakes import EchoCollector  # imported, must NOT be re-registered here

_SRC = Source(name="alpha_src", display_name="Alpha", kind=SourceKind.SYNTHETIC)

__all__ = ["AlphaCollector", "EchoCollector"]


class AbstractIntermediate(Collector):
    @abstractmethod
    async def helper(self) -> None: ...


class AlphaCollector(Collector):
    name: ClassVar[str] = "alpha"
    description: ClassVar[str] = "Alpha test collector."
    supported_targets: ClassVar[frozenset[TargetType]] = frozenset({TargetType.EMAIL})
    source: ClassVar[Source] = _SRC
    rate_limit: ClassVar[RateLimit] = RateLimit(requests=1, per_seconds=1)
    data_types: ClassVar[frozenset[FindingType]] = frozenset({FindingType.EMAIL})

    async def collect(self, target: Target) -> list[Finding]:
        return []
