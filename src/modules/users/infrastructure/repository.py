from typing import cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import User as UserModel


class UserRepository(GenericSQLRepository[UserModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel)

    async def get_by_email(self, email: str) -> UserModel | None:
        condition = cast(ColumnElement[bool], UserModel.email == email)
        stmt = select(UserModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def get_by_ci(self, ci: str) -> UserModel | None:
        condition = cast(ColumnElement[bool], UserModel.ci == ci)
        stmt = select(UserModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().first()
