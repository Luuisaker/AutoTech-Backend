from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import UserPaymentAccount as UserPaymentAccountModel


class UserPaymentAccountRepository(GenericSQLRepository[UserPaymentAccountModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserPaymentAccountModel)

    async def list_by_user(self, user_id: str) -> Sequence[UserPaymentAccountModel]:
        condition = cast(
            ColumnElement[bool], UserPaymentAccountModel.user_id == user_id
        )
        stmt = (
            select(UserPaymentAccountModel)
            .where(condition)
            .order_by(UserPaymentAccountModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()
