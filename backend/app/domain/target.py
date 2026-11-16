"""Target: the seed of an investigation (what the user typed, plus optional pivots)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.enums import TargetType
from app.domain.validation import (
    is_valid_domain,
    is_valid_email,
    is_valid_phone,
    is_valid_username,
    validate_target_value,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=256)]
TargetValue = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2048)
]


def utc_now() -> datetime:
    return datetime.now(UTC)


class TargetSeeds(BaseModel):
    """Extra pivots for PERSON / ORGANIZATION targets (SPECS.md §5 "Persona").

    Seeds are only used as starting points for queries on public sources; they are never
    asserted as facts about the subject.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    first_name: ShortText | None = None
    last_name: ShortText | None = None
    usernames: list[ShortText] = Field(default_factory=list, max_length=10)
    emails: list[ShortText] = Field(default_factory=list, max_length=10)
    phones: list[ShortText] = Field(default_factory=list, max_length=10)
    related_domains: list[ShortText] = Field(default_factory=list, max_length=10)

    @model_validator(mode="after")
    def _check_seeds(self) -> Self:
        bad = (
            [u for u in self.usernames if not is_valid_username(u)]
            + [e for e in self.emails if not is_valid_email(e)]
            + [p for p in self.phones if not is_valid_phone(p)]
            + [d for d in self.related_domains if not is_valid_domain(d)]
        )
        if bad:
            raise ValueError(f"invalid seed values: {bad}")
        return self

    def is_empty(self) -> bool:
        return not (
            self.first_name
            or self.last_name
            or self.usernames
            or self.emails
            or self.phones
            or self.related_domains
        )


class Target(BaseModel):
    """A thing to investigate. `value` is kept exactly as entered (after trimming)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    type: TargetType
    value: TargetValue
    seeds: TargetSeeds | None = None
    parent_target_id: UUID | None = Field(
        default=None, description="Set when this target was created by pivoting from another."
    )
    pivot_depth: int = Field(default=0, ge=0)
    created_at: AwareDatetime = Field(default_factory=utc_now)

    @model_validator(mode="after")
    def _check_value(self) -> Self:
        if not validate_target_value(self.type, self.value):
            raise ValueError(f"{self.value!r} is not a valid {self.type.value}")
        if self.seeds is not None:
            if self.type not in {TargetType.PERSON, TargetType.ORGANIZATION}:
                raise ValueError("seeds are only allowed for person/organization targets")
            if self.seeds.is_empty():
                raise ValueError("seeds, when given, must contain at least one value")
        if (self.parent_target_id is None) != (self.pivot_depth == 0):
            raise ValueError("pivot_depth > 0 if and only if parent_target_id is set")
        return self
