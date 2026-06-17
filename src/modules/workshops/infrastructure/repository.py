from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import Workshop as WorkshopModel


class WorkshopRepository(GenericSQLRepository[WorkshopModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkshopModel)

    async def get_by_rif(self, rif: str) -> WorkshopModel | None:
        condition = cast(ColumnElement[bool], WorkshopModel.rif == rif)
        stmt = select(WorkshopModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def list_by_owner(self, owner_id: str) -> Sequence[WorkshopModel]:
        condition = cast(ColumnElement[bool], WorkshopModel.owner_id == owner_id)
        stmt = select(WorkshopModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def search(
        self,
        query: str | None = None,
        certified_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[WorkshopModel]:
        stmt = select(WorkshopModel)
        where_clauses: list = []

        if query:
            like_pattern = f"%{query}%"
            where_clauses.append(
                cast(ColumnElement[bool], WorkshopModel.name.ilike(like_pattern))
            )

        if certified_only:
            where_clauses.append(
                cast(ColumnElement[bool], WorkshopModel.is_certified == 1)
            )

        if where_clauses:
            stmt = stmt.where(*where_clauses)

        stmt = stmt.limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.scalars().all()
