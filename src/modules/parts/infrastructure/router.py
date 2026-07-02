from uuid import UUID
from fastapi import Depends, APIRouter, Response, Query, File, UploadFile
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.parts.infrastructure.service import (
    PartService,
    get_part_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id
from src.modules.users.infrastructure.permissions import require_workshop_owner
from src.utils.handle_service_result import handle_service_result
from src.utils.file_upload import save_upload_file
from src.modules.parts.application.create import (
    CreatePartRequest,
    UpdatePartRequest,
    PurchasePartRequest,
    RecordPaymentRequest,
    PartDTO,
    PartListDTO,
    PartCategoryListDTO,
    PartPurchaseDTO,
    PartPurchaseListDTO,
    PartPaymentDTO,
    PartPaymentListDTO,
)


class PartRouter(BaseRouter):
    __prefix__ = "/parts"
    __tag__ = "Parts"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.get(
            "/categories", response_model=CoreResponse[PartCategoryListDTO]
        )
        async def part_categories():
            return PartService.get_categories()

        @self._router.get(
            "/conditions", response_model=CoreResponse[PartCategoryListDTO]
        )
        async def part_conditions():
            return PartService.get_conditions()

        @self._router.post("", response_model=CoreResponse[PartDTO], status_code=201)
        async def create(
            body: CreatePartRequest,
            response: Response,
            service: PartService = Depends(get_part_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            result = await service.create(body, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.get("", response_model=CoreResponse[PartListDTO])
        async def list_parts(
            response: Response,
            query: str | None = Query(default=None),
            category: str | None = Query(default=None),
            condition: str | None = Query(default=None),
            min_price: float | None = Query(default=None, ge=0),
            max_price: float | None = Query(default=None, ge=0),
            certified_only: bool = Query(default=False),
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: PartService = Depends(get_part_service),
        ):
            result = await service.list(
                query=query,
                category=category,
                condition=condition,
                min_price=min_price,
                max_price=max_price,
                certified_only=certified_only,
                offset=offset,
                limit=limit,
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/workshop/{workshop_id}", response_model=CoreResponse[PartListDTO]
        )
        async def list_workshop_parts(
            workshop_id: UUID,
            response: Response,
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: PartService = Depends(get_part_service),
        ):
            result = await service.list_by_workshop(workshop_id, offset, limit)
            handle_service_result(result, response)
            return result

        @self._router.get("/{id}", response_model=CoreResponse[PartDTO])
        async def get_part(
            id: UUID,
            response: Response,
            service: PartService = Depends(get_part_service),
        ):
            result = await service.get_by_id(id)
            handle_service_result(result, response)
            return result

        @self._router.put("/{id}", response_model=CoreResponse[PartDTO])
        async def update_part(
            id: UUID,
            body: UpdatePartRequest,
            response: Response,
            service: PartService = Depends(get_part_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            result = await service.update(id, body, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.delete("/{id}", response_model=CoreResponse)
        async def deactivate_part(
            id: UUID,
            response: Response,
            service: PartService = Depends(get_part_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            result = await service.deactivate(id, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.post("/{id}/photo", response_model=CoreResponse[PartDTO])
        async def upload_part_photo(
            id: UUID,
            response: Response,
            photo: UploadFile = File(...),
            service: PartService = Depends(get_part_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            photo_url = await save_upload_file(photo, "part_photos")
            result = await service.upload_photo(id, current_user.id, photo_url)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/{id}/purchase",
            response_model=CoreResponse[PartPurchaseDTO],
            status_code=201,
        )
        async def purchase_part(
            id: UUID,
            body: PurchasePartRequest,
            response: Response,
            service: PartService = Depends(get_part_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            body.part_id = id
            result = await service.purchase(body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/purchases/mine", response_model=CoreResponse[PartPurchaseListDTO]
        )
        async def my_purchases(
            response: Response,
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: PartService = Depends(get_part_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list_purchases_by_user(user_id, offset, limit)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/purchases/{purchase_id}/payments",
            response_model=CoreResponse[PartPaymentListDTO],
        )
        async def purchase_payments(
            purchase_id: UUID,
            response: Response,
            service: PartService = Depends(get_part_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_purchase_payments(purchase_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/payments/{payment_id}/pay",
            response_model=CoreResponse[PartPaymentDTO],
        )
        async def pay_payment(
            payment_id: UUID,
            body: RecordPaymentRequest,
            response: Response,
            service: PartService = Depends(get_part_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.record_payment(payment_id, user_id, body)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/workshop/{workshop_id}/sales",
            response_model=CoreResponse[PartPurchaseListDTO],
        )
        async def workshop_sales(
            workshop_id: UUID,
            response: Response,
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: PartService = Depends(get_part_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            result = await service.list_workshop_sales(
                workshop_id, current_user.id, offset, limit
            )
            handle_service_result(result, response)
            return result
