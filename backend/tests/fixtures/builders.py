"""Builders for domain objects used by persistence tests (reserved example values only)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain import (
    Evidence,
    EvidenceKind,
    Finding,
    FindingType,
    NormalizationStep,
    ProvenanceKind,
    Source,
    SourceKind,
)
from tests.conftest import FIXED_NOW


def make_source(name: str = "dns", *, synthetic: bool = False) -> Source:
    return Source(
        name=name,
        display_name=name.upper(),
        kind=SourceKind.DNS,
        is_synthetic=synthetic,
    )


def make_evidence(investigation_id: UUID, **overrides: Any) -> Evidence:
    data: dict[str, Any] = {
        "investigation_id": investigation_id,
        "kind": EvidenceKind.DNS_RESPONSE,
        "source": "dns",
        "collector": "dns_records",
        "request_summary": "DNS A example.com",
        "retrieved_at": FIXED_NOW,
        "content": '{"A": ["192.0.2.1"]}',
    }
    data.update(overrides)
    return Evidence(**data)


def make_finding(
    investigation_id: UUID,
    *,
    evidence: Evidence | None = None,
    **overrides: Any,
) -> Finding:
    """OBSERVED IP finding with a normalization step; attaches `evidence` when given."""
    data: dict[str, Any] = {
        "type": FindingType.IP_ADDRESS,
        "value": "192.0.2.1 ",
        "normalized_value": "192.0.2.1",
        "raw_value": {"address": "192.0.2.1 ", "ttl": 300},
        "normalization_steps": [
            NormalizationStep(operation="strip", input="192.0.2.1 ", output="192.0.2.1")
        ],
        "source": "dns",
        "timestamp": FIXED_NOW,
        "confidence": 0.9,
        "collector": "dns_records",
        "investigation_id": investigation_id,
        "provenance_kind": ProvenanceKind.OBSERVED,
        "metadata": {"record": "A"},
    }
    if "value" in overrides and "normalization_steps" not in overrides:
        data["normalization_steps"] = []
        data["normalized_value"] = overrides["value"]
    data.update(overrides)
    if evidence is not None:
        data["evidence"] = evidence
    return Finding(**data)
