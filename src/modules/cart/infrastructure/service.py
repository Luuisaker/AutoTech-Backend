from typing import Type
from uuid import UUID
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.cart.infrastructure.mapper import CartMapper, CartItemMapper
from src.modules.cart.application.create import (
    AddToCartRequest,
    CartDTO,
    CartItemDetailDTO,
)
from src.modules.cart.domain.entity import Cart, CartItem
from src.modules.cart.infrastructure.repository import (
    CartRepository,
    CartItemRepository,
)
from src.modules.parts.infrastructure.repository import PartRepository
from src.config.models import Cart as CartModel
from src.config.models import Part as PartModel
from src.config.models import Workshop as WorkshopModel
from sqlalchemy import select


class CartService:
    __cart_mapper = CartMapper()
    __item_mapper = CartItemMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    async def _ensure_cart(self, t, user_id: UUID) -> CartModel:
        cart = await t.cart.get_by_user(str(user_id))
        if not cart:
            cart_entity = Cart(user_id=user_id)
            cart = await t.cart.add(self.__cart_mapper.to_model(cart_entity))
        return cart

    async def add_item(self, dto: AddToCartRequest, user_id: UUID) -> Response:
        async with self._transaction(
            cart=CartRepository,
            cart_item=CartItemRepository,
            part=PartRepository,
        ) as t:
            p_model = await t.part.get(str(dto.part_id))
            if not p_model or not p_model.is_active:
                return Response(
                    status_code=404,
                    success=False,
                    message="Producto no encontrado o no disponible",
                )
            if p_model.stock < dto.quantity:
                return Response(
                    status_code=400,
                    success=False,
                    message="Stock insuficiente",
                )

            cart = await self._ensure_cart(t, user_id)

            existing = await t.cart_item.get_by_cart_and_part(
                str(cart.id), str(dto.part_id)
            )
            if existing:
                existing.quantity += dto.quantity
                await t.cart_item.update(existing)
            else:
                item_entity = CartItem(
                    cart_id=cart.id, part_id=dto.part_id, quantity=dto.quantity
                )
                await t.cart_item.add(self.__item_mapper.to_model(item_entity))

        return Response(
            status_code=200,
            success=True,
            message="Producto agregado al carrito",
        )

    async def remove_item(self, item_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            cart=CartRepository,
            cart_item=CartItemRepository,
        ) as t:
            item = await t.cart_item.get(str(item_id))
            if not item:
                return Response(
                    status_code=404,
                    success=False,
                    message="Item no encontrado",
                )

            cart = await t.cart.get(str(item.cart_id))
            if not cart or cart.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a este carrito",
                )

            await t.cart_item._session.delete(item)

        return Response(
            status_code=200,
            success=True,
            message="Producto eliminado del carrito",
        )

    async def view_cart(self, user_id: UUID) -> Response:
        async with self._transaction(
            cart=CartRepository,
        ) as t:
            cart = await t.cart.get_by_user(str(user_id))
            if not cart or not cart.items:
                return Response(
                    status_code=200,
                    success=True,
                    content=CartDTO(id=None, items=[], total=0.0),
                )

            # Fetch part + workshop details for each item
            items_detail = []
            total = 0.0
            for ci in cart.items:
                stmt = (
                    select(PartModel, WorkshopModel)
                    .join(WorkshopModel, PartModel.workshop_id == WorkshopModel.id)
                    .where(PartModel.id == ci.part_id)
                )
                r = await t.cart._session.execute(stmt)
                row = r.one_or_none()
                if row:
                    p, w = row
                    subtotal = p.price * ci.quantity
                    total += subtotal
                    items_detail.append(
                        CartItemDetailDTO(
                            id=ci.id,
                            part_id=ci.part_id,
                            part_name=p.name,
                            part_price=p.price,
                            workshop_id=w.id,
                            workshop_name=w.name,
                            quantity=ci.quantity,
                            subtotal=subtotal,
                        )
                    )

        return Response(
            status_code=200,
            success=True,
            content=CartDTO(id=cart.id, items=items_detail, total=round(total, 2)),
        )

    async def clear_cart(self, user_id: UUID) -> Response:
        async with self._transaction(cart=CartRepository) as t:
            cart = await t.cart.get_by_user(str(user_id))
            if cart:
                for item in cart.items:
                    await t.cart._session.delete(item)
                await t.cart._session.delete(cart)

        return Response(
            status_code=200,
            success=True,
            message="Carrito vaciado",
        )


def get_cart_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> CartService:
    return CartService(transaction)
