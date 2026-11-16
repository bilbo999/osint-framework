"""Fake collectors shared by tests. No network access."""

from __future__ import annotations

import json
from typing import ClassVar

from app.collectors.base import Collector
from app.domain import (
    EvidenceKind,
    Finding,
    FindingType,
    RateLimit,
    Source,
    SourceKind,
    Target,
    TargetType,
)

FAKE_SOURCE = Source(
    name="fake_source", display_name="Fake source", kind=SourceKind.SYNTHETIC, is_synthetic=True
)


class EchoCollector(Collector):
    """Returns the target value as a single OBSERVED finding with evidence."""

    name: ClassVar[str] = "echo"
    description: ClassVar[str] = "Echoes the target (test double)."
    supported_targets: ClassVar[frozenset[TargetType]] = frozenset({TargetType.DOMAIN})
    source: ClassVar[Source] = FAKE_SOURCE
    rate_limit: ClassVar[RateLimit] = RateLimit(requests=10, per_seconds=1)
    data_types: ClassVar[frozenset[FindingType]] = frozenset({FindingType.DOMAIN})

    async def collect(self, target: Target) -> list[Finding]:
        evidence = self.new_evidence(
            target,
            kind=EvidenceKind.SYNTHETIC,
            content=json.dumps({"echo": target.value}),
            request_summary=f"echo {target.value}",
        )
        return [
            self.new_finding(
                target,
                type=FindingType.DOMAIN,
                value=target.value,
                raw_value={"echo": target.value},
                evidence=evidence,
            )
        ]
