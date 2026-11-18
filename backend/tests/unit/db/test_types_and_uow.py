"""Column types, engine setup and the Unit of Work."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.types import JSONType, UTCDateTime
from app.db.uow import UnitOfWork
from app.domain.enums import InvestigationStatus
from app.domain.records import Investigation
from app.models import InvestigationRow
from tests.conftest import FIXED_NOW


def test_utc_datetime_rejects_naive() -> None:
    with pytest.raises(ValueError, match="naive"):
        UTCDateTime().process_bind_param(datetime(2026, 1, 1), None)  # type: ignore[arg-type]


def test_utc_datetime_normalizes_offsets_to_utc() -> None:
    plus2 = datetime(2026, 1, 1, 14, 0, tzinfo=timezone(timedelta(hours=2)))
    bound = UTCDateTime().process_bind_param(plus2, None)  # type: ignore[arg-type]
    assert bound == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    assert bound is not None
    assert bound.utcoffset() == timedelta(0)


async def test_utc_datetime_round_trip_returns_aware_utc_on_sqlite(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_factory() as session:
        session.add(
            InvestigationRow(
                id=Investigation(name="x").id,
                name="x",
                status=InvestigationStatus.DRAFT,
                is_synthetic=False,
                created_at=FIXED_NOW,
                updated_at=FIXED_NOW,
            )
        )
        await session.commit()
        row = (await session.execute(sa.select(InvestigationRow))).scalar_one()
        await session.refresh(row)
    assert row.created_at == FIXED_NOW
    assert row.created_at.tzinfo is not None
    assert row.created_at.utcoffset() == timedelta(0)


def test_json_type_uses_jsonb_on_postgresql_only() -> None:
    from sqlalchemy.dialects import postgresql, sqlite

    pg_impl = JSONType.dialect_impl(postgresql.dialect())  # type: ignore[no-untyped-call]
    sqlite_impl = JSONType.dialect_impl(sqlite.dialect())
    assert pg_impl.__class__.__name__.endswith("JSONB")
    assert "JSONB" not in sqlite_impl.__class__.__name__.upper()


async def test_sqlite_engine_enforces_foreign_keys(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        assert (await conn.execute(sa.text("PRAGMA foreign_keys"))).scalar_one() == 1


async def test_uow_rolls_back_without_commit(
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    inv = Investigation(name="draft", created_at=FIXED_NOW, updated_at=FIXED_NOW)
    async with uow_factory() as uow:
        await uow.investigations.add(inv)  # no commit
    async with uow_factory() as uow:
        assert await uow.investigations.get(inv.id) is None


async def test_uow_rolls_back_on_error_and_commits_on_request(
    uow_factory: Callable[[], UnitOfWork],
) -> None:
    kept = Investigation(name="kept", created_at=FIXED_NOW, updated_at=FIXED_NOW)
    lost = Investigation(name="lost", created_at=FIXED_NOW, updated_at=FIXED_NOW)
    async with uow_factory() as uow:
        await uow.investigations.add(kept)
        await uow.commit()

    async def failing_transaction() -> None:
        async with uow_factory() as uow:
            await uow.investigations.add(lost)
            raise RuntimeError("boom")

    with pytest.raises(RuntimeError, match="boom"):
        await failing_transaction()
    async with uow_factory() as uow:
        assert await uow.investigations.get(kept.id) is not None
        assert await uow.investigations.get(lost.id) is None


async def test_uow_explicit_rollback_and_misuse(uow_factory: Callable[[], UnitOfWork]) -> None:
    inv = Investigation(name="rb", created_at=FIXED_NOW, updated_at=FIXED_NOW)
    async with uow_factory() as uow:
        await uow.investigations.add(inv)
        await uow.rollback()
        await uow.commit()
        assert await uow.investigations.get(inv.id) is None
    with pytest.raises(RuntimeError, match="outside"):
        await uow_factory().commit()
