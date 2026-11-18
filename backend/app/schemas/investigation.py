"""Minimal API DTOs for investigations (full CRUD endpoints arrive in Phase 8)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

from app.domain.enums import InvestigationStatus, TargetType
from app.domain.records import Investigation
from app.domain.target import TargetSeeds, TargetValue


class InvestigationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
    description: str | None = Field(default=None, max_length=4000)
    is_synthetic: bool = False


class InvestigationRead(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    name: str
    description: str | None
    status: InvestigationStatus
    is_synthetic: bool
    created_at: AwareDatetime
    updated_at: AwareDatetime
    closed_at: AwareDatetime | None

    @classmethod
    def from_domain(cls, investigation: Investigation) -> InvestigationRead:
        return cls.model_validate(investigation)


class TargetCreate(BaseModel):
    """Input for adding a target. Value validation per type happens in the `Target` domain model."""

    model_config = ConfigDict(extra="forbid")

    type: TargetType
    value: TargetValue
    seeds: TargetSeeds | None = None
