from typing import Type
from uuid import UUID
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.workshops.infrastructure.mapper import (
    WorkshopMapper,
    WorkshopBankAccountMapper,
    WorkshopMobilePaymentMapper,
)
from src.modules.workshops.application.create import (
    CreateWorkshopRequest,
    UpdateWorkshopRequest,
    WorkshopDTO,
    WorkshopListDTO,
    VerificationRequestDTO,
    VerificationRequestListDTO,
    CreateBankAccountRequest,
    UpdateBankAccountRequest,
    BankAccountDTO,
    BankAccountListDTO,
    CreateMobilePaymentRequest,
    UpdateMobilePaymentRequest,
    MobilePaymentDTO,
    MobilePaymentListDTO,
    WorkshopBankListDTO,
)
from src.modules.workshops.domain.entity import (
    Workshop,
    WorkshopBankAccount,
    WorkshopMobilePayment,
)
from src.modules.workshops.domain.types import VenezuelanBank
from src.modules.workshops.infrastructure.repository import (
    WorkshopRepository,
    WorkshopBankAccountRepository,
    WorkshopMobilePaymentRepository,
)
from src.modules.users.infrastructure.repository import UserRepository
from src.config.models import UserRole


class WorkshopService:
    __mapper = WorkshopMapper()
    __bank_account_mapper = WorkshopBankAccountMapper()
    __mobile_payment_mapper = WorkshopMobilePaymentMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    async def create(
        self,
        dto: CreateWorkshopRequest,
        owner_id: UUID,
        verification_document_url: str | None,
        photo_url: str | None,
    ) -> Response:
        async with self._transaction(workshop=WorkshopRepository, user=UserRepository) as t:
            if await t.workshop.get_by_rif(dto.rif):
                return Response(
                    status_code=400,
                    success=False,
                    message="El RIF ya está registrado",
                )

            workshop_entity = Workshop(
                owner_id=owner_id,
                name=dto.name,
                rif=dto.rif,
                address=dto.address,
                latitude=dto.latitude,
                longitude=dto.longitude,
                verification_document_url=verification_document_url,
                photo_url=photo_url,
            )

            w_model = await t.workshop.add(self.__mapper.to_model(workshop_entity))

            owner = await t.user.get(str(owner_id))
            if owner and "ADMIN" not in [ur.role for ur in owner.roles]:
                if not any(ur.role == "WORKSHOP_OWNER" for ur in owner.roles):
                    owner.roles.append(UserRole(role="WORKSHOP_OWNER", user_id=owner.id))
                    await t.user.update(owner)

        return Response(
            status_code=201,
            success=True,
            message="Taller registrado exitosamente",
            content=WorkshopDTO.model_validate(self.__mapper.to_entity(w_model)),
        )

    async def list(
        self,
        query: str | None = None,
        certified_only: bool = False,
        owner_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            workshops = await t.workshop.search(
                query=query,
                certified_only=certified_only,
                owner_id=str(owner_id) if owner_id else None,
                offset=offset,
                limit=limit,
            )

        return Response(
            status_code=200,
            success=True,
            content=WorkshopListDTO(
                workshops=[
                    WorkshopDTO.model_validate(self.__mapper.to_entity(w))
                    for w in workshops
                ]
            ),
        )

    async def list_pending_verifications(self) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            workshops = await t.workshop.list_pending_verifications()

        return Response(
            status_code=200,
            success=True,
            content=VerificationRequestListDTO(
                requests=[
                    VerificationRequestDTO(
                        id=w.id,
                        owner_id=w.owner_id,
                        owner_first_name=w.owner.first_name,
                        owner_last_name=w.owner.last_name,
                        owner_email=w.owner.email,
                        name=w.name,
                        rif=w.rif,
                        address=w.address,
                        verification_document_url=w.verification_document_url,
                        created_at=w.created_at,
                    )
                    for w in workshops
                ]
            ),
        )

    async def get_by_id(self, workshop_id: UUID) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(workshop_id))

        if not w_model:
            return Response(
                status_code=404,
                success=False,
                message="Taller no encontrado",
            )

        return Response(
            status_code=200,
            success=True,
            content=WorkshopDTO.model_validate(self.__mapper.to_entity(w_model)),
        )

    async def update(
        self,
        workshop_id: UUID,
        dto: UpdateWorkshopRequest,
        owner_id: UUID,
        verification_document_url: str | None = None,
        photo_url: str | None = None,
    ) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(workshop_id))

        if not w_model:
            return Response(
                status_code=404,
                success=False,
                message="Taller no encontrado",
            )

        if w_model.owner_id != owner_id:
            return Response(
                status_code=403,
                success=False,
                message="No eres el dueño de este taller",
            )

        if dto.name is not None:
            w_model.name = dto.name
        if dto.address is not None:
            w_model.address = dto.address
        if dto.latitude is not None:
            w_model.latitude = dto.latitude
        if dto.longitude is not None:
            w_model.longitude = dto.longitude
        if verification_document_url is not None:
            w_model.verification_document_url = verification_document_url
        if photo_url is not None:
            w_model.photo_url = photo_url

        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.update(w_model)

        return Response(
            status_code=200,
            success=True,
            message="Taller actualizado exitosamente",
            content=WorkshopDTO.model_validate(self.__mapper.to_entity(w_model)),
        )

    async def delete(self, workshop_id: UUID, owner_id: UUID) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(workshop_id))

        if not w_model:
            return Response(
                status_code=404,
                success=False,
                message="Taller no encontrado",
            )

        if w_model.owner_id != owner_id:
            return Response(
                status_code=403,
                success=False,
                message="No eres el dueño de este taller",
            )

        async with self._transaction(workshop=WorkshopRepository) as t:
            await t.workshop.delete(w_model)

        return Response(
            status_code=200,
            success=True,
            message="Taller eliminado exitosamente",
        )

    async def upload_photo(
        self, workshop_id: UUID, owner_id: UUID, photo_url: str
    ) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(workshop_id))

        if not w_model:
            return Response(
                status_code=404,
                success=False,
                message="Taller no encontrado",
            )

        if w_model.owner_id != owner_id:
            return Response(
                status_code=403,
                success=False,
                message="No eres el dueño de este taller",
            )

        w_model.photo_url = photo_url

        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.update(w_model)

        return Response(
            status_code=200,
            success=True,
            message="Foto del taller actualizada",
            content=WorkshopDTO.model_validate(self.__mapper.to_entity(w_model)),
        )

    async def get_by_id_admin(self, workshop_id: UUID) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(workshop_id))

        if not w_model:
            return Response(
                status_code=404,
                success=False,
                message="Taller no encontrado",
            )

        return Response(
            status_code=200,
            success=True,
            content=WorkshopDTO.model_validate(self.__mapper.to_entity(w_model)),
        )

    async def certify(self, workshop_id: UUID) -> Response:
        async with self._transaction(
            workshop=WorkshopRepository, user=UserRepository
        ) as t:
            w_model = await t.workshop.get(str(workshop_id))

            if not w_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Taller no encontrado",
                )

            w_model.is_certified = 1

            owner = await t.user.get(str(w_model.owner_id))
            if owner and "ADMIN" not in [ur.role for ur in owner.roles]:
                if not any(ur.role == "WORKSHOP_OWNER" for ur in owner.roles):
                    owner.roles.append(
                        UserRole(role="WORKSHOP_OWNER", user_id=owner.id)
                    )
                await t.user.update(owner)

        return Response(
            status_code=200,
            success=True,
            message="Taller certificado exitosamente",
            content=WorkshopDTO.model_validate(self.__mapper.to_entity(w_model)),
        )

    @staticmethod
    def get_banks() -> Response:
        return Response(
            status_code=200,
            success=True,
            content=WorkshopBankListDTO(banks=[b.value for b in VenezuelanBank]),
        )

    async def create_bank_account(
        self, workshop_id: UUID, dto: CreateBankAccountRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(workshop_id))

            if not w_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Taller no encontrado",
                )

            if w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

        entity = WorkshopBankAccount(
            workshop_id=workshop_id,
            account_number=dto.account_number,
            holder_ci=dto.holder_ci,
            bank_name=dto.bank_name,
        )

        async with self._transaction(bank_account=WorkshopBankAccountRepository) as t:
            model = await t.bank_account.add(
                self.__bank_account_mapper.to_model(entity)
            )

        return Response(
            status_code=201,
            success=True,
            message="Cuenta bancaria registrada exitosamente",
            content=BankAccountDTO.model_validate(
                self.__bank_account_mapper.to_entity(model)
            ),
        )

    async def list_bank_accounts(self, workshop_id: UUID) -> Response:
        async with self._transaction(bank_account=WorkshopBankAccountRepository) as t:
            accounts = await t.bank_account.list_by_workshop(str(workshop_id))

        return Response(
            status_code=200,
            success=True,
            content=BankAccountListDTO(
                accounts=[
                    BankAccountDTO.model_validate(
                        self.__bank_account_mapper.to_entity(a)
                    )
                    for a in accounts
                ]
            ),
        )

    async def update_bank_account(
        self,
        account_id: UUID,
        workshop_id: UUID,
        dto: UpdateBankAccountRequest,
        user_id: UUID,
    ) -> Response:
        async with self._transaction(
            bank_account=WorkshopBankAccountRepository,
            workshop=WorkshopRepository,
        ) as t:
            a_model = await t.bank_account.get(str(account_id))

            if not a_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Cuenta bancaria no encontrada",
                )

            if a_model.workshop_id != workshop_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="Esta cuenta no pertenece a tu taller",
                )

            w_model = await t.workshop.get(str(workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            if dto.account_number is not None:
                a_model.account_number = dto.account_number
            if dto.holder_ci is not None:
                a_model.holder_ci = dto.holder_ci
            if dto.bank_name is not None:
                a_model.bank_name = dto.bank_name
            if dto.is_active is not None:
                a_model.is_active = dto.is_active

            a_model = await t.bank_account.update(a_model)

        return Response(
            status_code=200,
            success=True,
            message="Cuenta bancaria actualizada exitosamente",
            content=BankAccountDTO.model_validate(
                self.__bank_account_mapper.to_entity(a_model)
            ),
        )

    async def delete_bank_account(
        self, account_id: UUID, workshop_id: UUID, user_id: UUID
    ) -> Response:
        async with self._transaction(
            bank_account=WorkshopBankAccountRepository,
            workshop=WorkshopRepository,
        ) as t:
            a_model = await t.bank_account.get(str(account_id))

            if not a_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Cuenta bancaria no encontrada",
                )

            if a_model.workshop_id != workshop_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="Esta cuenta no pertenece a tu taller",
                )

            w_model = await t.workshop.get(str(workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            a_model.is_active = 0
            await t.bank_account.update(a_model)

        return Response(
            status_code=200,
            success=True,
            message="Cuenta bancaria desactivada exitosamente",
        )

    async def create_mobile_payment(
        self, workshop_id: UUID, dto: CreateMobilePaymentRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(workshop_id))

            if not w_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Taller no encontrado",
                )

            if w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

        entity = WorkshopMobilePayment(
            workshop_id=workshop_id,
            phone_number=dto.phone_number,
            bank_name=dto.bank_name,
            holder_ci=dto.holder_ci,
        )

        async with self._transaction(
            mobile_payment=WorkshopMobilePaymentRepository
        ) as t:
            model = await t.mobile_payment.add(
                self.__mobile_payment_mapper.to_model(entity)
            )

        return Response(
            status_code=201,
            success=True,
            message="Pago móvil registrado exitosamente",
            content=MobilePaymentDTO.model_validate(
                self.__mobile_payment_mapper.to_entity(model)
            ),
        )

    async def list_mobile_payments(self, workshop_id: UUID) -> Response:
        async with self._transaction(
            mobile_payment=WorkshopMobilePaymentRepository
        ) as t:
            payments = await t.mobile_payment.list_by_workshop(str(workshop_id))

        return Response(
            status_code=200,
            success=True,
            content=MobilePaymentListDTO(
                payments=[
                    MobilePaymentDTO.model_validate(
                        self.__mobile_payment_mapper.to_entity(p)
                    )
                    for p in payments
                ]
            ),
        )

    async def update_mobile_payment(
        self,
        payment_id: UUID,
        workshop_id: UUID,
        dto: UpdateMobilePaymentRequest,
        user_id: UUID,
    ) -> Response:
        async with self._transaction(
            mobile_payment=WorkshopMobilePaymentRepository,
            workshop=WorkshopRepository,
        ) as t:
            p_model = await t.mobile_payment.get(str(payment_id))

            if not p_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Pago móvil no encontrado",
                )

            if p_model.workshop_id != workshop_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="Este pago móvil no pertenece a tu taller",
                )

            w_model = await t.workshop.get(str(workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            if dto.phone_number is not None:
                p_model.phone_number = dto.phone_number
            if dto.bank_name is not None:
                p_model.bank_name = dto.bank_name
            if dto.holder_ci is not None:
                p_model.holder_ci = dto.holder_ci
            if dto.is_active is not None:
                p_model.is_active = dto.is_active

            p_model = await t.mobile_payment.update(p_model)

        return Response(
            status_code=200,
            success=True,
            message="Pago móvil actualizado exitosamente",
            content=MobilePaymentDTO.model_validate(
                self.__mobile_payment_mapper.to_entity(p_model)
            ),
        )

    async def delete_mobile_payment(
        self, payment_id: UUID, workshop_id: UUID, user_id: UUID
    ) -> Response:
        async with self._transaction(
            mobile_payment=WorkshopMobilePaymentRepository,
            workshop=WorkshopRepository,
        ) as t:
            p_model = await t.mobile_payment.get(str(payment_id))

            if not p_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Pago móvil no encontrado",
                )

            if p_model.workshop_id != workshop_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="Este pago móvil no pertenece a tu taller",
                )

            w_model = await t.workshop.get(str(workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            p_model.is_active = 0
            await t.mobile_payment.update(p_model)

        return Response(
            status_code=200,
            success=True,
            message="Pago móvil desactivado exitosamente",
        )


def get_workshop_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> WorkshopService:
    return WorkshopService(transaction)
