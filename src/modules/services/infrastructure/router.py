from uuid import UUID
from fastapi import Depends, APIRouter, Response, Query
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.services.infrastructure.service import (
    ServiceService,
    get_service_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id, CurrentUser
from src.modules.users.infrastructure.permissions import require_workshop_owner, require_admin
from src.utils.handle_service_result import handle_service_result
from src.modules.services.application.create import (
    CreateServiceRequest,
    UpdateServiceRequest,
    ServiceDTO,
    ServiceListDTO,
    ServiceWithWorkshopListDTO,
    CreateServiceOrderRequest,
    SetQuoteRequest,
    SetRevisionRequest,
    UpdateServiceOrderStatusRequest,
    AddExtraChargeRequest,
    MarkServiceShippedRequest,
    RateServiceOrderRequest,
    PayServiceOrderRequest,
    ServiceOrderDTO,
    ServiceOrderListDTO,
    AdminServiceOrderDetailDTO,
)


class ServiceRouter(BaseRouter):
    __prefix__ = "/services"
    __tag__ = "Services"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.post("", response_model=CoreResponse[ServiceDTO], status_code=201)
        async def create(
            body: CreateServiceRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            result = await service.create(body, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.get("", response_model=CoreResponse[ServiceListDTO])
        async def search_services(
            response: Response,
            query: str | None = Query(default=None),
            min_price: float | None = Query(default=None, ge=0),
            max_price: float | None = Query(default=None, ge=0),
            certified_only: bool = Query(default=True),
            service_type: str | None = Query(default=None),
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: ServiceService = Depends(get_service_service),
        ):
            result = await service.search(
                query=query,
                min_price=min_price,
                max_price=max_price,
                certified_only=certified_only,
                service_type=service_type,
                offset=offset,
                limit=limit,
            )
            handle_service_result(result, response)
            return result

        @self._router.get("/with-workshops", response_model=CoreResponse[ServiceWithWorkshopListDTO])
        async def services_with_workshops(
            response: Response,
            query: str | None = Query(default=None),
            certified_only: bool = Query(default=True),
            service_type: str | None = Query(default=None),
            workshop_id: UUID | None = Query(default=None),
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: ServiceService = Depends(get_service_service),
        ):
            result = await service.search_with_workshops(
                query=query,
                service_type=service_type,
                certified_only=certified_only,
                workshop_id=workshop_id,
                offset=offset,
                limit=limit,
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/workshop/{workshop_id}", response_model=CoreResponse[ServiceListDTO]
        )
        async def list_workshop_services(
            workshop_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
        ):
            result = await service.list_by_workshop(workshop_id)
            handle_service_result(result, response)
            return result

        @self._router.get("/{id}", response_model=CoreResponse[ServiceDTO])
        async def get_service(
            id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
        ):
            result = await service.get_by_id(id)
            handle_service_result(result, response)
            return result

        @self._router.put("/{id}", response_model=CoreResponse[ServiceDTO])
        async def update_service(
            id: UUID,
            body: UpdateServiceRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            result = await service.update(id, body, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.delete("/{id}", response_model=CoreResponse)
        async def delete_service(
            id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: tuple = Depends(require_workshop_owner),
        ):
            result = await service.delete(id, current_user.id)
            handle_service_result(result, response)
            return result

        # -- Service Orders --

        @self._router.post(
            "/orders",
            response_model=CoreResponse[ServiceOrderDTO],
            status_code=201,
        )
        async def create_service_order(
            body: CreateServiceOrderRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.create_service_order(body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/orders/mine",
            response_model=CoreResponse[ServiceOrderListDTO],
        )
        async def my_service_orders(
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list_my_service_orders(user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/orders/workshop/{workshop_id}",
            response_model=CoreResponse[ServiceOrderListDTO],
        )
        async def workshop_service_orders(
            workshop_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.list_workshop_service_orders(
                workshop_id, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/orders/{order_id}",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def get_service_order(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_service_order(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get(
            "/orders/admin/{order_id}",
            response_model=CoreResponse[AdminServiceOrderDetailDTO],
        )
        async def admin_get_service_order(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: tuple = Depends(require_admin),
        ):
            result = await service.admin_get_service_order(order_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/mark-at-workshop",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def mark_at_workshop(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.mark_at_workshop(order_id, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/mark-dropped-off",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def mark_dropped_off(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.mark_dropped_off(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/set-revision",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def set_revision(
            order_id: UUID,
            body: SetRevisionRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.set_revision(order_id, body, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/accept-revision",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def accept_revision(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.accept_revision(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/reject-revision",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def reject_revision(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.reject_revision(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/set-quote",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def set_quote(
            order_id: UUID,
            body: SetQuoteRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.set_quote(order_id, body, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/accept-quote",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def accept_quote(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.accept_quote(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/reject-quote",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def reject_quote(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.reject_quote(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/mark-delivered",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def mark_delivered(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.mark_delivered(order_id, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.put(
            "/orders/{order_id}/status",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def update_service_order_status(
            order_id: UUID,
            body: UpdateServiceOrderStatusRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_service_order_status(
                order_id, body, current_user.id
            )
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/extra-charge",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def add_extra_charge(
            order_id: UUID,
            body: AddExtraChargeRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.add_extra_charge(order_id, body, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/approve-extra",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def approve_extra_charge(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.approve_extra_charge(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/reject-extra",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def reject_extra_charge(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.reject_extra_charge(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/mark-shipped",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def mark_shipped(
            order_id: UUID,
            body: MarkServiceShippedRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.mark_service_shipped(order_id, current_user.id, body)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/mark-received",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def mark_received(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.mark_service_received(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/cancel",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def cancel_service_order(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.cancel_service_order(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/close-client",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def close_client(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.close_service_as_client(order_id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/close-workshop",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def close_workshop(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.close_service_as_workshop(order_id, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/pay",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def pay_service_order(
            order_id: UUID,
            body: PayServiceOrderRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.pay_service_order(order_id, body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/confirm-payment",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def confirm_service_payment(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.confirm_service_payment(order_id, current_user.id)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/rate-workshop",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def rate_workshop(
            order_id: UUID,
            body: RateServiceOrderRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.rate_service_order_workshop(order_id, user_id, body)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/rate-client",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def rate_client(
            order_id: UUID,
            body: RateServiceOrderRequest,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.rate_service_order_client(order_id, current_user.id, body)
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/mark-in-progress",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def mark_in_progress(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_service_order_status(
                order_id,
                UpdateServiceOrderStatusRequest(status="IN_PROGRESS"),
                current_user.id,
            )
            handle_service_result(result, response)
            return result

        @self._router.post(
            "/orders/{order_id}/mark-completed",
            response_model=CoreResponse[ServiceOrderDTO],
        )
        async def mark_completed(
            order_id: UUID,
            response: Response,
            service: ServiceService = Depends(get_service_service),
            current_user: CurrentUser = Depends(require_workshop_owner),
        ):
            result = await service.update_service_order_status(
                order_id,
                UpdateServiceOrderStatusRequest(status="COMPLETED"),
                current_user.id,
            )
            handle_service_result(result, response)
            return result
