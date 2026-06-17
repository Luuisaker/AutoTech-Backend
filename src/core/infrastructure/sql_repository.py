from typing import Type, TypeVar, Sequence, cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.domain.repository import GenericRepository

T = TypeVar("T")


class GenericSQLRepository(GenericRepository[T]):
    def __init__(self, session: AsyncSession, model_cls: Type[T]) -> None:
        self._session = session
        self._model_cls = model_cls

    # Constructing SQL statements
    def _construct_get_stmt(self, id_: str):
        condition = cast(ColumnElement[bool], getattr(self._model_cls, "id") == id_)
        return select(self._model_cls).where(condition)

    def _construct_list_stmt(self, offset: int, limit: int, **filters):
        stmt = select(self._model_cls)
        where_clauses: list[ColumnElement[bool]] = []

        for column, value in filters.items():
            if not hasattr(self._model_cls, column):
                raise ValueError(f"Invalid column name {column}")

            model_column = getattr(self._model_cls, column)

            if isinstance(value, str):
                where_clauses.append(
                    cast(ColumnElement[bool], model_column.ilike(f"%{value}%"))
                )
            else:
                where_clauses.append(cast(ColumnElement[bool], model_column == value))

        if where_clauses:
            stmt = stmt.where(*where_clauses)

        stmt = stmt.limit(limit).offset(offset)

        return stmt

    # CRUD
    async def add(self, record: T) -> T:
        self._session.add(record)
        await self._session.flush()
        return record

    async def get(self, id_: str) -> T | None:
        stmt = self._construct_get_stmt(id_)
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def list(self, offset: int = 0, limit: int = 100, **filters) -> Sequence[T]:
        stmt = self._construct_list_stmt(offset, limit, **filters)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def update(self, record: T) -> T:
        self._session.add(record)
        await self._session.flush()
        return record
