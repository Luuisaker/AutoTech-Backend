from uuid import UUID
from fastapi import Depends, APIRouter, Response, Query
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.orders.infrastructure.service import (
    OrderService,
    get_order_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id
from src.utils.handle_service_result import handle_service_result
from src.modules.orders.application.create import (
    CheckoutRequest,
    PayInstallmentRequest,
    OrderDTO,
    OrderListDTO,
    InstallmentListDTO,
    InstallmentDTO,
)


class OrderRouter(BaseRouter):
    __prefix__ = "/orders"
    __tag__ = "Orders"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.post(
            "/checkout",
            response_model=CoreResponse[OrderDTO],
            status_code=201,
        )
        async def checkout(
            body: CheckoutRequest,
            response: Response,
            service: OrderService = Depends(get_order_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.checkout(body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get("/mine", response_model=CoreResponse[OrderListDTO])
        async def my_orders(
            response: Response,
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: OrderService = Depends(get_order_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list_mine(user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{order_id}/installments",
            response_model=CoreResponse[InstallmentListDTO],
        )
        async def order_installments(
            order_id: UUID,
            response: Response,
            service: OrderService = Depends(get_order_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_installments(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/installments/{installment_id}/pay",
            response_model=CoreResponse[InstallmentDTO],
        )
        async def pay_installment(
            installment_id: UUID,
            body: PayInstallmentRequest,
            response: Response,
            service: OrderService = Depends(get_order_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.pay_installment(installment_id, user_id, body)
            handle_service_result(result, response)
            return result
