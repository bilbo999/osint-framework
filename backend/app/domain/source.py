"""Source: where data comes from (a public service, a protocol, a local parser)."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_.-]{1,63}$")]


class SourceKind(StrEnum):
    DNS = "dns"
    RDAP = "rdap"
    TLS = "tls"
    CERTIFICATE_TRANSPARENCY = "certificate_transparency"
    HTTP_API = "http_api"
    PUBLIC_WEB = "public_web"
    LOCAL_DATABASE = "local_database"
    LOCAL_PARSER = "local_parser"
    SYNTHETIC = "synthetic"


class Source(BaseModel):
    """Static description of a data source.

    `name` is the stable key used by Finding.source, Evidence.source and
    config/scoring.yaml `confidence.source_reliability`. Reliability is NOT stored here:
    it is configuration, never code.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: Slug
    display_name: Annotated[str, StringConstraints(min_length=1, max_length=128)]
    kind: SourceKind
    homepage_url: str | None = None
    terms_url: str | None = None
    requires_api_key: bool = False
    is_synthetic: bool = False
