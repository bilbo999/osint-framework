"""Evidence: the raw material a finding was extracted from (provenance anchor)."""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.domain.source import Slug


class EvidenceKind(StrEnum):
    DNS_RESPONSE = "dns_response"
    RDAP_RESPONSE = "rdap_response"
    HTTP_RESPONSE = "http_response"
    API_RESPONSE = "api_response"
    TLS_CERTIFICATE = "tls_certificate"
    CT_LOG_ENTRY = "ct_log_entry"
    COMPUTED = "computed"
    SYNTHETIC = "synthetic"


def sha256_hex(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class Evidence(BaseModel):
    """Immutable capture of what a source returned.

    `content` must already be sanitised by the collector: no API keys, cookies or
    authorization headers. `sha256` is computed automatically and verified if supplied,
    so tampering is detectable. Size limits are enforced by the persistence layer from
    config/settings.yaml (`evidence.max_content_bytes`).
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID = Field(default_factory=uuid4)
    investigation_id: UUID
    kind: EvidenceKind
    source: Slug
    collector: Slug
    source_url: Annotated[str, StringConstraints(max_length=2048)] | None = None
    request_summary: Annotated[str, StringConstraints(max_length=2048)] | None = Field(
        default=None, description='Human-readable request, e.g. "DNS A example.com". No secrets.'
    )
    retrieved_at: AwareDatetime
    content_type: str = "application/json"
    content: str
    sha256: str = ""
    is_synthetic: bool = False

    @model_validator(mode="after")
    def _check_hash(self) -> Self:
        digest = sha256_hex(self.content)
        if not self.sha256:
            object.__setattr__(self, "sha256", digest)
        elif self.sha256 != digest:
            raise ValueError("sha256 does not match content")
        return self
