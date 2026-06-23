from uuid import UUID
from fastapi import Depends, APIRouter, Response, Query
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.services.infrastructure.service import (
    ServiceService,
    get_service_service,
)
from src.modules.users.infrastructure.permissions import require_workshop_owner
from src.utils.handle_service_result import handle_service_result
from src.modules.services.application.create import (
    CreateServiceRequest,
    UpdateServiceRequest,
    ServiceDTO,
    ServiceListDTO,
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
            certified_only: bool = Query(default=False),
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            service: ServiceService = Depends(get_service_service),
        ):
            result = await service.search(
                query=query,
                min_price=min_price,
                max_price=max_price,
                certified_only=certified_only,
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
