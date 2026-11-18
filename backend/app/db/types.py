"""Portable column types (PostgreSQL in production, SQLite in unit tests)."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Dialect


class UTCDateTime(sa.TypeDecorator[datetime]):
    """Timezone-aware datetime that always comes back as UTC (SQLite drops the tzinfo).

    Naive datetimes are rejected on write: every timestamp in the system is UTC-aware.
    """

    impl = sa.DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("naive datetime rejected: use timezone-aware (UTC) datetimes")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


#: JSON everywhere, JSONB on PostgreSQL. Python ``None`` is stored as JSON ``null``.
JSONType = sa.JSON().with_variant(JSONB(), "postgresql")
#: Same, but Python ``None`` is stored as SQL ``NULL`` (for optional columns).
NullableJSONType = sa.JSON(none_as_null=True).with_variant(JSONB(none_as_null=True), "postgresql")


def enum_column(enum_cls: type[StrEnum]) -> sa.Enum:
    """Non-native enum stored as VARCHAR(32) holding the enum *values*.

    Adding a value to the enum needs no schema migration (see ADR-003).
    """
    return sa.Enum(
        enum_cls,
        native_enum=False,
        length=32,
        create_constraint=False,
        values_callable=lambda cls: [member.value for member in cls],
        validate_strings=True,
    )
