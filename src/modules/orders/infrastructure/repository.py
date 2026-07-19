from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import joinedload, selectinload

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import Order as OrderModel
from src.config.models import OrderItem as OrderItemModel
from src.config.models import Installment as InstallmentModel
from src.config.models import Transaction as TransactionModel
from src.config.models import Part as PartModel
from src.config.models import OrderReview as OrderReviewModel


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
            .options(
                selectinload(OrderModel.items).selectinload(OrderItemModel.part).selectinload(PartModel.workshop),
                selectinload(OrderModel.installments),
                selectinload(OrderModel.order_reviews),
                selectinload(OrderModel.user),
            )
            .order_by(OrderModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def get_with_items(self, order_id: str) -> OrderModel | None:
        stmt = (
            select(OrderModel)
            .where(cast(ColumnElement[bool], OrderModel.id == order_id))
            .options(
                joinedload(OrderModel.items).joinedload(OrderItemModel.part).joinedload(PartModel.workshop),
                joinedload(OrderModel.installments),
                joinedload(OrderModel.user),
                joinedload(OrderModel.order_reviews),
            )
        )
        r = await self._session.execute(stmt)
        return r.unique().scalars().first()

    async def list_by_workshop(self, workshop_id: str) -> Sequence[OrderModel]:
        stmt = (
            select(OrderModel)
            .options(
                selectinload(OrderModel.items).selectinload(OrderItemModel.part).selectinload(PartModel.workshop),
                selectinload(OrderModel.installments),
                selectinload(OrderModel.user),
                selectinload(OrderModel.order_reviews),
            )
            .join(OrderItemModel, OrderItemModel.order_id == OrderModel.id)
            .where(cast(ColumnElement[bool], OrderItemModel.workshop_id == workshop_id))
            .order_by(OrderModel.created_at.desc())
            .distinct()
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()


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
        stmt = select(InstallmentModel).where(condition).order_by(InstallmentModel.due_date.asc().nulls_first())
        r = await self._session.execute(stmt)
        return r.scalars().all()


class TransactionRepository(GenericSQLRepository[TransactionModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, TransactionModel)
