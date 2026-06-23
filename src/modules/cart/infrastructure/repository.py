from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.orm import joinedload

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import Cart as CartModel
from src.config.models import CartItem as CartItemModel


class CartRepository(GenericSQLRepository[CartModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CartModel)

    async def get_by_user(self, user_id: str) -> CartModel | None:
        condition = cast(ColumnElement[bool], CartModel.user_id == user_id)
        stmt = select(CartModel).where(condition).options(joinedload(CartModel.items))
        r = await self._session.execute(stmt)
        return r.unique().scalars().first()

    async def get_with_items(self, cart_id: str) -> CartModel | None:
        stmt = (
            select(CartModel)
            .where(cast(ColumnElement[bool], CartModel.id == cart_id))
            .options(joinedload(CartModel.items))
        )
        r = await self._session.execute(stmt)
        return r.unique().scalars().first()


class CartItemRepository(GenericSQLRepository[CartItemModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CartItemModel)

    async def list_by_cart(self, cart_id: str) -> Sequence[CartItemModel]:
        condition = cast(ColumnElement[bool], CartItemModel.cart_id == cart_id)
        stmt = select(CartItemModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def get_by_cart_and_part(
        self, cart_id: str, part_id: str
    ) -> CartItemModel | None:
        condition = cast(
            ColumnElement[bool],
            (CartItemModel.cart_id == cart_id) & (CartItemModel.part_id == part_id),
        )
        stmt = select(CartItemModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().first()
