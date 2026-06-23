from uuid import UUID
from fastapi import Depends, APIRouter, Response
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.payments.infrastructure.service import (
    PaymentService,
    get_payment_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id
from src.utils.handle_service_result import handle_service_result
from src.modules.payments.application.create import (
    CreatePaymentAccountRequest,
    UpdatePaymentAccountRequest,
    UserPaymentAccountDTO,
    UserPaymentAccountListDTO,
)


class PaymentRouter(BaseRouter):
    __prefix__ = "/payments"
    __tag__ = "Payments"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.get("/banks", response_model=CoreResponse)
        async def list_banks():
            return PaymentService.get_banks()

        @self._router.get("/account-types", response_model=CoreResponse)
        async def list_account_types():
            return PaymentService.get_account_types()

        @self._router.get(
            "/accounts/mine", response_model=CoreResponse[UserPaymentAccountListDTO]
        )
        async def my_accounts(
            response: Response,
            service: PaymentService = Depends(get_payment_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list_mine(user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/accounts",
            response_model=CoreResponse[UserPaymentAccountDTO],
            status_code=201,
        )
        async def create_account(
            body: CreatePaymentAccountRequest,
            response: Response,
            service: PaymentService = Depends(get_payment_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.create(body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/accounts/{account_id}",
            response_model=CoreResponse[UserPaymentAccountDTO],
        )
        async def update_account(
            account_id: UUID,
            body: UpdatePaymentAccountRequest,
            response: Response,
            service: PaymentService = Depends(get_payment_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.update(account_id, body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.delete("/accounts/{account_id}", response_model=CoreResponse)
        async def delete_account(
            account_id: UUID,
            response: Response,
            service: PaymentService = Depends(get_payment_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.delete(account_id, user_id)
            handle_service_result(result, response)
            return result
