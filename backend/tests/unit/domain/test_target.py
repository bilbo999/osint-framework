"""Target / TargetType / TargetSeeds."""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.domain import Target, TargetSeeds, TargetType

VALID = [
    (TargetType.DOMAIN, "example.com"),
    (TargetType.DOMAIN, "münchen.example"),
    (TargetType.IP_ADDRESS, "192.0.2.10"),
    (TargetType.IP_ADDRESS, "2001:db8::1"),
    (TargetType.EMAIL, "alice@example.org"),
    (TargetType.USERNAME, "alice_01"),
    (TargetType.PHONE, "+1 555 0100 123"),
    (TargetType.URL, "https://www.example.com/path?q=1"),
    (TargetType.ORGANIZATION, "Example Corp"),
]
INVALID = [
    (TargetType.DOMAIN, "localhost"),
    (TargetType.DOMAIN, "-bad-.example"),
    (TargetType.IP_ADDRESS, "999.1.1.1"),
    (TargetType.EMAIL, "no-at-sign.example.com"),
    (TargetType.EMAIL, "a@b@example.com"),
    (TargetType.USERNAME, "has space"),
    (TargetType.PHONE, "12"),
    (TargetType.URL, "ftp://example.com"),
    (TargetType.URL, "javascript:alert(1)"),
    (TargetType.ORGANIZATION, "bad\x00name"),
]


def test_target_type_values_are_stable() -> None:
    assert {t.value for t in TargetType} == {
        "person",
        "organization",
        "domain",
        "ip_address",
        "email",
        "username",
        "phone",
        "url",
    }


@pytest.mark.parametrize(("target_type", "value"), VALID)
def test_valid_targets(investigation_id: UUID, target_type: TargetType, value: str) -> None:
    target = Target(investigation_id=investigation_id, type=target_type, value=f"  {value} ")
    assert target.value == value  # trimmed, otherwise untouched (normalization is Phase 4a)
    assert target.created_at.tzinfo is not None


@pytest.mark.parametrize(("target_type", "value"), INVALID)
def test_invalid_targets(investigation_id: UUID, target_type: TargetType, value: str) -> None:
    with pytest.raises(ValidationError):
        Target(investigation_id=investigation_id, type=target_type, value=value)


def test_person_with_seeds(investigation_id: UUID) -> None:
    seeds = TargetSeeds(
        first_name="Alex",
        last_name="Example",
        usernames=["alexexample"],
        emails=["alex@example.org"],
        related_domains=["example.org"],
    )
    target = Target(
        investigation_id=investigation_id, type=TargetType.PERSON, value="Alex Example", seeds=seeds
    )
    assert target.seeds == seeds


def test_seeds_rejected_for_non_person(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="seeds are only allowed"):
        Target(
            investigation_id=investigation_id,
            type=TargetType.DOMAIN,
            value="example.com",
            seeds=TargetSeeds(first_name="X"),
        )


def test_empty_seeds_rejected(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="at least one value"):
        Target(
            investigation_id=investigation_id,
            type=TargetType.PERSON,
            value="X",
            seeds=TargetSeeds(),
        )


def test_invalid_seed_values_rejected() -> None:
    with pytest.raises(ValidationError, match="invalid seed values"):
        TargetSeeds(emails=["not-an-email"])


def test_pivot_depth_requires_parent(investigation_id: UUID) -> None:
    with pytest.raises(ValidationError, match="pivot_depth"):
        Target(
            investigation_id=investigation_id,
            type=TargetType.DOMAIN,
            value="example.com",
            pivot_depth=1,
        )
    child = Target(
        investigation_id=investigation_id,
        type=TargetType.DOMAIN,
        value="example.com",
        parent_target_id=uuid4(),
        pivot_depth=1,
    )
    assert child.pivot_depth == 1


def test_target_is_immutable(domain_target: Target) -> None:
    with pytest.raises(ValidationError):
        domain_target.value = "other.example"  # type: ignore[misc]
