from uuid import UUID
from fastapi import Depends, APIRouter, Response, Form, File, UploadFile
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.workshops.infrastructure.service import (
    WorkshopService,
    get_workshop_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id, CurrentUser
from src.modules.users.infrastructure.permissions import (
    require_admin,
    require_workshop_owner,
)
from src.utils.handle_service_result import handle_service_result
from src.utils.file_upload import save_upload_file
from src.modules.workshops.application.create import (
    CreateWorkshopRequest,
    UpdateWorkshopRequest,
    WorkshopDTO,
    WorkshopListDTO,
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
    CreatePaymentMethodRequest,
    UpdatePaymentMethodRequest,
    PaymentMethodDTO,
    PaymentMethodListDTO,
    RateWorkshopRequest,
)


class WorkshopRouter(BaseRouter):
    __prefix__ = "/workshops"
    __tag__ = "Workshops"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.post(
            "", response_model=CoreResponse[WorkshopDTO], status_code=201
        )
        async def create(
            response: Response,
            name: str = Form(...),
            rif: str = Form(...),
            address: str = Form(...),
            latitude: float | None = Form(None),
            longitude: float | None = Form(None),
            verification_document: UploadFile | None = File(None),
            photo: UploadFile | None = File(None),
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            body = CreateWorkshopRequest(
                name=name,
                rif=rif,
                address=address,
                latitude=latitude,
                longitude=longitude,
            )
            doc_url = None
            if verification_document:
                doc_url = await save_upload_file(
                    verification_document, "verification_documents"
                )
            photo_url = None
            if photo:
                photo_url = await save_upload_file(photo, "workshop_photos")
            result = await service.create(body, user_id, doc_url, photo_url)
            handle_service_result(result, response)
            return result

        @self._router.get("", response_model=CoreResponse[WorkshopListDTO])
        async def list_workshops(
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            query: str | None = None,
            certified_only: bool = False,
            owned: bool = False,
            offset: int = 0,
            limit: int = 100,
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list(
                query=query,
                certified_only=certified_only,
                owner_id=user_id if owned else None,
                offset=offset,
                limit=limit,
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/verifications/pending",
            response_model=CoreResponse[VerificationRequestListDTO],
        )
        async def list_pending_verifications(
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            _: CurrentUser = Depends(require_admin),
        ):
            result = await service.list_pending_verifications()
            handle_service_result(result, response)
            return result

        @self._router.get("/banks", response_model=CoreResponse[WorkshopBankListDTO])
        async def list_banks():
            return WorkshopService.get_banks()

        @self._router.get("/{id}", response_model=CoreResponse[WorkshopDTO])
        async def get_workshop(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.get_by_id(id)
            handle_service_result(result, response)
            return result

        @self._router.put("/{id}", response_model=CoreResponse[WorkshopDTO])
        async def update_workshop(
            id: UUID,
            response: Response,
            name: str | None = Form(None),
            address: str | None = Form(None),
            latitude: float | None = Form(None),
            longitude: float | None = Form(None),
            verification_document: UploadFile | None = File(None),
            photo: UploadFile | None = File(None),
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            body = UpdateWorkshopRequest(
                name=name,
                address=address,
                latitude=latitude,
                longitude=longitude,
            )
            doc_url = None
            if verification_document:
                doc_url = await save_upload_file(
                    verification_document, "verification_documents"
                )
            photo_url = None
            if photo:
                photo_url = await save_upload_file(photo, "workshop_photos")
            result = await service.update(id, body, user_id, doc_url, photo_url)
            handle_service_result(result, response)
            return result

        @self._router.delete("/{id}", response_model=CoreResponse)
        async def delete_workshop(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.delete(id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/{id}/toggle-suspension",
            response_model=CoreResponse[WorkshopDTO],
            status_code=200,
        )
        async def toggle_workshop_suspension(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.toggle_suspension(id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post("/{id}/photo", response_model=CoreResponse[WorkshopDTO])
        async def upload_workshop_photo(
            id: UUID,
            response: Response,
            photo: UploadFile = File(...),
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            photo_url = await save_upload_file(photo, "workshop_photos")
            result = await service.upload_photo(id, user_id, photo_url)
            handle_service_result(result, response)
            return result

        @self._router.delete("/{id}/photo", response_model=CoreResponse[WorkshopDTO])
        async def delete_workshop_photo(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.delete_photo(id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{id}/verification",
            response_model=CoreResponse[WorkshopDTO],
        )
        async def get_workshop_verification(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            _: CurrentUser = Depends(require_admin),
        ):
            result = await service.get_by_id_admin(id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/{id}/certify",
            response_model=CoreResponse[WorkshopDTO],
            status_code=200,
        )
        async def certify_workshop(
            id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            _: CurrentUser = Depends(require_admin),
        ):
            result = await service.certify(id)
            handle_service_result(result, response)
            return result

        # -- Bank Accounts --

        @self._router.post(
            "/{workshop_id}/bank-accounts",
            response_model=CoreResponse[BankAccountDTO],
            status_code=201,
        )
        async def create_bank_account(
            workshop_id: UUID,
            body: CreateBankAccountRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.create_bank_account(
                workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{workshop_id}/bank-accounts",
            response_model=CoreResponse[BankAccountListDTO],
        )
        async def list_bank_accounts(
            workshop_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.list_bank_accounts(workshop_id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/{workshop_id}/bank-accounts/{account_id}",
            response_model=CoreResponse[BankAccountDTO],
        )
        async def update_bank_account(
            workshop_id: UUID,
            account_id: UUID,
            body: UpdateBankAccountRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_bank_account(
                account_id, workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.delete(
            "/{workshop_id}/bank-accounts/{account_id}",
            response_model=CoreResponse,
        )
        async def delete_bank_account(
            workshop_id: UUID,
            account_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.delete_bank_account(
                account_id, workshop_id, current_user.id
            )
            handle_service_result(result, response)
            return result

        # -- Mobile Payments --

        @self._router.post(
            "/{workshop_id}/mobile-payments",
            response_model=CoreResponse[MobilePaymentDTO],
            status_code=201,
        )
        async def create_mobile_payment(
            workshop_id: UUID,
            body: CreateMobilePaymentRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.create_mobile_payment(
                workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{workshop_id}/mobile-payments",
            response_model=CoreResponse[MobilePaymentListDTO],
        )
        async def list_mobile_payments(
            workshop_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.list_mobile_payments(workshop_id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/{workshop_id}/mobile-payments/{payment_id}",
            response_model=CoreResponse[MobilePaymentDTO],
        )
        async def update_mobile_payment(
            workshop_id: UUID,
            payment_id: UUID,
            body: UpdateMobilePaymentRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_mobile_payment(
                payment_id, workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.delete(
            "/{workshop_id}/mobile-payments/{payment_id}",
            response_model=CoreResponse,
        )
        async def delete_mobile_payment(
            workshop_id: UUID,
            payment_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.delete_mobile_payment(
                payment_id, workshop_id, current_user.id
            )
            handle_service_result(result, response)
            return result

        # -- Payment Methods --

        @self._router.post(
            "/{workshop_id}/payment-methods",
            response_model=CoreResponse[PaymentMethodDTO],
            status_code=201,
        )
        async def create_payment_method(
            workshop_id: UUID,
            body: CreatePaymentMethodRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.create_payment_method(
                workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/{workshop_id}/payment-methods",
            response_model=CoreResponse[PaymentMethodListDTO],
        )
        async def list_payment_methods(
            workshop_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
        ):
            result = await service.list_payment_methods(workshop_id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/{workshop_id}/payment-methods/{method_id}",
            response_model=CoreResponse[PaymentMethodDTO],
        )
        async def update_payment_method(
            workshop_id: UUID,
            method_id: UUID,
            body: UpdatePaymentMethodRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_payment_method(
                method_id, workshop_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.delete(
            "/{workshop_id}/payment-methods/{method_id}",
            response_model=CoreResponse,
        )
        async def delete_payment_method(
            workshop_id: UUID,
            method_id: UUID,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.delete_payment_method(
                method_id, workshop_id, current_user.id
            )
            handle_service_result(result, response)
            return result

        # -- Ratings --

        @self._router.post(
            "/{workshop_id}/ratings",
            response_model=CoreResponse[None],
            status_code=201,
        )
        async def rate_workshop(
            workshop_id: UUID,
            body: RateWorkshopRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.rate_workshop(workshop_id, user_id, body)
            handle_service_result(result, response)
            return result
