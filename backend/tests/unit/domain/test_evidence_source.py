"""Evidence integrity and Source validation."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain import Evidence, EvidenceKind, Source, SourceKind
from app.domain.evidence import sha256_hex
from tests.conftest import FIXED_NOW


def _evidence(investigation_id: UUID, **overrides: object) -> Evidence:
    data: dict[str, object] = {
        "investigation_id": investigation_id,
        "kind": EvidenceKind.DNS_RESPONSE,
        "source": "dns",
        "collector": "dns_records",
        "retrieved_at": FIXED_NOW,
        "content": '{"answer": []}',
    }
    data.update(overrides)
    return Evidence.model_validate(data)


def test_hash_is_computed(investigation_id: UUID) -> None:
    evidence = _evidence(investigation_id)
    assert evidence.sha256 == sha256_hex('{"answer": []}')


def test_matching_hash_accepted(investigation_id: UUID) -> None:
    assert _evidence(investigation_id, sha256=sha256_hex('{"answer": []}')).sha256


def test_tampered_hash_rejected(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="sha256"):
        _evidence(investigation_id, sha256="0" * 64)


def test_naive_datetime_rejected(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError):
        _evidence(investigation_id, retrieved_at=FIXED_NOW.replace(tzinfo=None))


def test_evidence_is_immutable(investigation_id: UUID) -> None:
    evidence = _evidence(investigation_id)
    with pytest.raises(ValidationError):
        evidence.content = "changed"  # type: ignore[misc]


@pytest.mark.parametrize("name", ["dns", "team_cymru", "github_api", "a.b-c"])
def test_valid_source_names(name: str) -> None:
    assert Source(name=name, display_name="X", kind=SourceKind.DNS).name == name


@pytest.mark.parametrize("name", ["", "D", "UPPER", "with space", "-leading"])
def test_invalid_source_names(name: str) -> None:
    with pytest.raises(ValidationError):
        Source(name=name, display_name="X", kind=SourceKind.DNS)
