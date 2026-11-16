"""Finding contract: provenance, normalization traceability, evidence linkage, secrets."""

from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.domain import (
    EntityType,
    Evidence,
    EvidenceKind,
    Finding,
    FindingType,
    NormalizationStep,
    ProvenanceKind,
    RelationHint,
    RelationType,
)
from tests.conftest import FIXED_NOW


@pytest.fixture
def evidence(investigation_id: UUID) -> Evidence:
    return Evidence(
        investigation_id=investigation_id,
        kind=EvidenceKind.DNS_RESPONSE,
        source="dns",
        collector="dns_records",
        retrieved_at=FIXED_NOW,
        content='{"A": ["192.0.2.1"]}',
    )


def make(investigation_id: UUID, **overrides: Any) -> Finding:
    data: dict[str, Any] = {
        "type": FindingType.IP_ADDRESS,
        "value": "192.0.2.1",
        "normalized_value": "192.0.2.1",
        "raw_value": "192.0.2.1",
        "source": "dns",
        "timestamp": FIXED_NOW,
        "confidence": 0.5,
        "collector": "dns_records",
        "investigation_id": investigation_id,
        "provenance_kind": ProvenanceKind.OBSERVED,
        "evidence_id": uuid4(),
    }
    data.update(overrides)
    return Finding.model_validate(data)


def test_spec_fields_present() -> None:
    spec_fields = {
        "id",
        "type",
        "value",
        "normalized_value",
        "source",
        "source_url",
        "timestamp",
        "confidence",
        "collector",
        "investigation_id",
        "evidence_id",
        "metadata",
        "provenance_kind",
        "raw_value",
        "normalization_steps",
    }
    assert spec_fields <= set(Finding.model_fields)


def test_provenance_kinds() -> None:
    assert [k.value for k in ProvenanceKind] == ["OBSERVED", "DERIVED", "INFERRED", "CORRELATED"]


def test_observed_finding_ok(investigation_id: UUID) -> None:
    finding = make(investigation_id)
    assert finding.is_fact
    assert finding.timestamp.tzinfo is not None


def test_observed_requires_evidence(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="OBSERVED findings require evidence"):
        make(investigation_id, evidence_id=None)


def test_observed_cannot_be_derived(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="cannot be derived_from"):
        make(investigation_id, derived_from=[uuid4()])


def test_derived_requires_evidence_or_parents(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="DERIVED findings require"):
        make(investigation_id, provenance_kind=ProvenanceKind.DERIVED, evidence_id=None)
    assert make(
        investigation_id,
        provenance_kind=ProvenanceKind.DERIVED,
        evidence_id=None,
        derived_from=[uuid4()],
    )


@pytest.mark.parametrize("kind", [ProvenanceKind.INFERRED, ProvenanceKind.CORRELATED])
def test_inferences_require_parents(investigation_id: UUID, kind: ProvenanceKind) -> None:
    with pytest.raises(ValidationError, match="require derived_from"):
        make(investigation_id, provenance_kind=kind)
    finding = make(investigation_id, provenance_kind=kind, derived_from=[uuid4()])
    assert not finding.is_fact


def test_cannot_derive_from_itself(investigation_id: UUID) -> None:
    fid = uuid4()
    with pytest.raises(ValidationError, match="itself"):
        make(investigation_id, id=fid, provenance_kind=ProvenanceKind.INFERRED, derived_from=[fid])


def test_assignment_is_validated(investigation_id: UUID) -> None:
    finding = make(investigation_id)
    with pytest.raises(ValidationError):
        finding.provenance_kind = ProvenanceKind.INFERRED  # no derived_from => invalid
    with pytest.raises(ValidationError):
        finding.confidence = 1.5


def test_normalization_chain(investigation_id: UUID) -> None:
    steps = [
        NormalizationStep(operation="strip", input=" Example.COM. ", output="Example.COM."),
        NormalizationStep(operation="lowercase", input="Example.COM.", output="example.com."),
        NormalizationStep(
            operation="strip_trailing_dot", input="example.com.", output="example.com"
        ),
    ]
    finding = make(
        investigation_id,
        type=FindingType.DOMAIN,
        value=" Example.COM. ",
        raw_value=" Example.COM. ",
        normalized_value="example.com",
        normalization_steps=steps,
    )
    assert finding.normalization_steps[-1].output == finding.normalized_value


def test_untracked_normalization_rejected(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="no steps recorded"):
        make(investigation_id, value="Example.com", normalized_value="example.com")


def test_broken_chain_rejected(investigation_id: UUID) -> None:
    steps = [
        NormalizationStep(operation="lowercase", input="A.example", output="a.example"),
        NormalizationStep(operation="strip", input="other", output="b.example"),
    ]
    with pytest.raises(ValidationError, match="not chained"):
        make(
            investigation_id,
            value="A.example",
            normalized_value="b.example",
            normalization_steps=steps,
        )


def test_attached_evidence_sets_id_and_is_not_serialized(
    investigation_id: UUID, evidence: Evidence
) -> None:
    finding = make(investigation_id, evidence_id=None, evidence=evidence)
    assert finding.evidence_id == evidence.id
    dumped = finding.model_dump()
    assert "evidence" not in dumped
    assert dumped["evidence_id"] == evidence.id


def test_mismatched_evidence_rejected(investigation_id: UUID, evidence: Evidence) -> None:
    with pytest.raises(ValidationError, match="does not match"):
        make(investigation_id, evidence=evidence)  # make() sets a different evidence_id
    with pytest.raises(ValidationError, match="different investigation"):
        make(uuid4(), evidence_id=None, evidence=evidence)


def test_synthetic_evidence_forces_synthetic_finding(
    investigation_id: UUID, evidence: Evidence
) -> None:
    synthetic = evidence.model_copy(update={"is_synthetic": True})
    with pytest.raises(ValidationError, match="synthetic"):
        make(investigation_id, evidence_id=None, evidence=synthetic)
    assert make(
        investigation_id, evidence_id=None, evidence=synthetic, is_synthetic=True
    ).is_synthetic


@pytest.mark.parametrize("key", ["api_key", "X-Api-Key", "password", "session_token", "Cookie"])
def test_secret_like_metadata_rejected(investigation_id: UUID, key: str) -> None:
    with pytest.raises(ValidationError, match="looks like a secret"):
        make(investigation_id, metadata={key: "x"})


def test_relation_hint_and_json_roundtrip(investigation_id: UUID) -> None:
    hint = RelationHint(
        subject_type=EntityType.DOMAIN,
        subject_value="example.com",
        relation=RelationType.RESOLVES_TO,
    )
    finding = make(
        investigation_id,
        relation_hint=hint,
        raw_value={"rdata": "192.0.2.1", "ttl": 300},
        metadata={"record_type": "A", "ttl": 300},
    )
    restored = Finding.model_validate_json(finding.model_dump_json())
    assert restored == finding


def test_confidence_bounds(investigation_id: UUID) -> None:
    for bad in (-0.1, 1.01):
        with pytest.raises(ValidationError):
            make(investigation_id, confidence=bad)


def test_unknown_fields_forbidden(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError):
        make(investigation_id, severity="high")
