"""Alembic against a REAL PostgreSQL. Skipped unless OSINT_TEST_DATABASE_URL is set.

WARNING: the target database is migrated up and DOWN (all tables dropped). Use a throw-away DB:
    OSINT_TEST_DATABASE_URL=postgresql+asyncpg://osint:...@localhost:5432/osint_test
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.config import Config

from alembic import command
from app.db.session import create_engine
from app.domain import FindingType
from app.domain.enums import InvestigationStatus
from app.models import FindingRow, InvestigationRow, SourceRow
from tests.conftest import FIXED_NOW

TEST_URL = os.environ.get("OSINT_TEST_DATABASE_URL", "")
BACKEND_DIR = Path(__file__).resolve().parents[2]

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not TEST_URL, reason="OSINT_TEST_DATABASE_URL not set"),
]


def _config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic").replace("%", "%%"))
    cfg.attributes["database_url"] = TEST_URL
    return cfg


async def _tables() -> set[str]:
    engine = create_engine(TEST_URL)
    try:
        async with engine.connect() as conn:
            names = await conn.run_sync(lambda c: set(sa.inspect(c).get_table_names()))
    finally:
        await engine.dispose()
    return names


@pytest.fixture
def migrated() -> Iterator[Config]:
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield cfg
    command.downgrade(cfg, "base")


def test_upgrade_downgrade_upgrade_roundtrip() -> None:
    cfg = _config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    assert {"investigations", "findings", "evidence", "graph_outbox"} <= asyncio.run(_tables())
    command.check(cfg)  # no model/migration drift
    command.downgrade(cfg, "base")
    assert asyncio.run(_tables()) <= {"alembic_version"}
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")


@pytest.mark.usefixtures("migrated")
def test_jsonb_insert_and_query_by_type() -> None:
    async def scenario() -> tuple[list[str], str]:
        engine = create_engine(TEST_URL)
        inv_id = uuid4()
        try:
            async with engine.begin() as conn:
                await conn.execute(
                    sa.insert(InvestigationRow).values(
                        id=inv_id,
                        name="pg",
                        status=InvestigationStatus.DRAFT,
                        is_synthetic=True,
                        created_at=FIXED_NOW,
                        updated_at=FIXED_NOW,
                    )
                )
                await conn.execute(
                    sa.insert(SourceRow).values(
                        name="dns",
                        display_name="DNS",
                        kind="dns",
                        is_synthetic=True,
                        requires_api_key=False,
                    )
                )
                common = {
                    "investigation_id": inv_id,
                    "source": "dns",
                    "timestamp": FIXED_NOW,
                    "confidence": 0.8,
                    "collector": "dns_records",
                    "provenance_kind": "DERIVED",
                    "derived_from": [],
                    "normalization_steps": [],
                    "is_synthetic": True,
                    "created_at": FIXED_NOW,
                }
                for ftype, value, raw in (
                    (FindingType.IP_ADDRESS, "192.0.2.1", {"a": {"ttl": 300}}),
                    (FindingType.DOMAIN, "example.com", {"a": {"ttl": 60}}),
                ):
                    await conn.execute(
                        sa.insert(FindingRow).values(
                            id=uuid4(),
                            type=ftype,
                            value=value,
                            normalized_value=value,
                            raw_value=raw,
                            metadata={"k": [1, 2]},
                            **common,
                        )
                    )
                rows = (
                    (
                        await conn.execute(
                            sa.select(FindingRow.normalized_value).where(
                                FindingRow.type == FindingType.IP_ADDRESS
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                # JSONB-specific operator, proves the column really is JSONB on PostgreSQL.
                ttl = (
                    await conn.execute(
                        sa.text(
                            "SELECT raw_value #>> '{a,ttl}' FROM findings " "WHERE type = 'domain'"
                        )
                    )
                ).scalar_one()
        finally:
            await engine.dispose()
        return list(rows), str(ttl)

    values, ttl = asyncio.run(scenario())
    assert values == ["192.0.2.1"]
    assert ttl == "60"
