from typing import Type
from uuid import UUID
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.payments.infrastructure.mapper import UserPaymentAccountMapper
from src.modules.payments.application.create import (
    CreatePaymentAccountRequest,
    UpdatePaymentAccountRequest,
    UserPaymentAccountDTO,
    UserPaymentAccountListDTO,
)
from src.modules.payments.domain.entity import UserPaymentAccount
from src.modules.payments.infrastructure.repository import (
    UserPaymentAccountRepository,
)
from src.modules.workshops.domain.types import VenezuelanBank


class PaymentService:
    __mapper = UserPaymentAccountMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    @staticmethod
    def get_banks() -> Response:
        return Response(
            status_code=200,
            success=True,
            content={"banks": [b.value for b in VenezuelanBank]},
        )

    @staticmethod
    def get_account_types() -> Response:
        from src.modules.payments.domain.types import PaymentAccountType

        return Response(
            status_code=200,
            success=True,
            content={"account_types": [t.value for t in PaymentAccountType]},
        )

    async def create(self, dto: CreatePaymentAccountRequest, user_id: UUID) -> Response:
        entity = UserPaymentAccount(
            user_id=user_id,
            account_type=dto.account_type,
            bank_name=dto.bank_name,
            holder_document=dto.holder_document,
            account_number=dto.account_number,
            account_holder=dto.account_holder,
            phone_number=dto.phone_number,
        )

        async with self._transaction(account=UserPaymentAccountRepository) as t:
            model = await t.account.add(self.__mapper.to_model(entity))

        return Response(
            status_code=201,
            success=True,
            message="Método de pago registrado exitosamente",
            content=UserPaymentAccountDTO.model_validate(
                self.__mapper.to_entity(model)
            ),
        )

    async def list_mine(self, user_id: UUID) -> Response:
        async with self._transaction(account=UserPaymentAccountRepository) as t:
            models = await t.account.list_by_user(str(user_id))

        return Response(
            status_code=200,
            success=True,
            content=UserPaymentAccountListDTO(
                accounts=[
                    UserPaymentAccountDTO.model_validate(self.__mapper.to_entity(m))
                    for m in models
                ]
            ),
        )

    async def update(
        self, account_id: UUID, dto: UpdatePaymentAccountRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(account=UserPaymentAccountRepository) as t:
            model = await t.account.get(str(account_id))

            if not model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Método de pago no encontrado",
                )

            if model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a este método de pago",
                )

            if dto.account_type is not None:
                model.account_type = dto.account_type
            if dto.bank_name is not None:
                model.bank_name = dto.bank_name
            if dto.holder_document is not None:
                model.holder_document = dto.holder_document
            if dto.account_number is not None:
                model.account_number = dto.account_number
            if dto.account_holder is not None:
                model.account_holder = dto.account_holder
            if dto.phone_number is not None:
                model.phone_number = dto.phone_number
            if dto.is_active is not None:
                model.is_active = dto.is_active

            model = await t.account.update(model)

        return Response(
            status_code=200,
            success=True,
            message="Método de pago actualizado exitosamente",
            content=UserPaymentAccountDTO.model_validate(
                self.__mapper.to_entity(model)
            ),
        )

    async def delete(self, account_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(account=UserPaymentAccountRepository) as t:
            model = await t.account.get(str(account_id))

            if not model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Método de pago no encontrado",
                )

            if model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a este método de pago",
                )

            model.is_active = 0
            await t.account.update(model)

        return Response(
            status_code=200,
            success=True,
            message="Método de pago desactivado exitosamente",
        )


def get_payment_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> PaymentService:
    return PaymentService(transaction)
