"""Base class for repositories: they own all SQL and return domain objects only."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
