from uuid import UUID
from fastapi import Depends, APIRouter, Response
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.cart.infrastructure.service import (
    CartService,
    get_cart_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id
from src.utils.handle_service_result import handle_service_result
from src.modules.cart.application.create import (
    AddToCartRequest,
    UpdateCartItemRequest,
    CartDTO,
    WorkshopBreakdownDTO,
)


class CartRouter(BaseRouter):
    __prefix__ = "/cart"
    __tag__ = "Cart"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.get("", response_model=CoreResponse[CartDTO])
        async def view_cart(
            response: Response,
            service: CartService = Depends(get_cart_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.view_cart(user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/workshop-breakdown",
            response_model=CoreResponse[WorkshopBreakdownDTO],
        )
        async def workshop_breakdown(
            response: Response,
            service: CartService = Depends(get_cart_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.workshop_breakdown(user_id)
            handle_service_result(result, response)
            return result

        @self._router.post("/add", response_model=CoreResponse, status_code=200)
        async def add_to_cart(
            body: AddToCartRequest,
            response: Response,
            service: CartService = Depends(get_cart_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.add_item(body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.put("/items/{item_id}", response_model=CoreResponse)
        async def update_cart_item(
            item_id: UUID,
            body: UpdateCartItemRequest,
            response: Response,
            service: CartService = Depends(get_cart_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.update_item_quantity(item_id, user_id, body)
            handle_service_result(result, response)
            return result

        @self._router.delete("/items/{item_id}", response_model=CoreResponse)
        async def remove_from_cart(
            item_id: UUID,
            response: Response,
            service: CartService = Depends(get_cart_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.remove_item(item_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.delete("", response_model=CoreResponse)
        async def clear_cart(
            response: Response,
            service: CartService = Depends(get_cart_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.clear_cart(user_id)
            handle_service_result(result, response)
            return result
