from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import joinedload

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import Order as OrderModel
from src.config.models import OrderItem as OrderItemModel
from src.config.models import Installment as InstallmentModel
from src.config.models import Transaction as TransactionModel


class OrderRepository(GenericSQLRepository[OrderModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrderModel)

    async def list_by_user(
        self, user_id: str, offset: int = 0, limit: int = 100
    ) -> Sequence[OrderModel]:
        condition = cast(ColumnElement[bool], OrderModel.user_id == user_id)
        stmt = (
            select(OrderModel)
            .where(condition)
            .options(joinedload(OrderModel.items))
            .order_by(OrderModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        r = await self._session.execute(stmt)
        return r.unique().scalars().all()

    async def get_with_items(self, order_id: str) -> OrderModel | None:
        stmt = (
            select(OrderModel)
            .where(cast(ColumnElement[bool], OrderModel.id == order_id))
            .options(joinedload(OrderModel.items))
        )
        r = await self._session.execute(stmt)
        return r.unique().scalars().first()


class OrderItemRepository(GenericSQLRepository[OrderItemModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, OrderItemModel)

    async def list_by_order(self, order_id: str) -> Sequence[OrderItemModel]:
        condition = cast(ColumnElement[bool], OrderItemModel.order_id == order_id)
        stmt = select(OrderItemModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()


class InstallmentRepository(GenericSQLRepository[InstallmentModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, InstallmentModel)

    async def list_by_order(self, order_id: str) -> Sequence[InstallmentModel]:
        condition = cast(ColumnElement[bool], InstallmentModel.order_id == order_id)
        stmt = select(InstallmentModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()


class TransactionRepository(GenericSQLRepository[TransactionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TransactionModel)
