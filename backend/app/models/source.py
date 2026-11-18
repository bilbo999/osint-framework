"""sources table: global catalogue of data sources, keyed by their slug."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import enum_column
from app.domain.source import SourceKind


class SourceRow(Base):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(sa.String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(sa.String(128))
    kind: Mapped[SourceKind] = mapped_column(enum_column(SourceKind))
    homepage_url: Mapped[str | None] = mapped_column(sa.String(2048))
    terms_url: Mapped[str | None] = mapped_column(sa.String(2048))
    requires_api_key: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    is_synthetic: Mapped[bool] = mapped_column(sa.Boolean, default=False)
