from uuid import UUID
from fastapi import Depends, APIRouter, Response
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.workshops.infrastructure.service import (
    WorkshopService,
    get_workshop_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id, CurrentUser
from src.modules.users.infrastructure.permissions import require_admin
from src.utils.handle_service_result import handle_service_result
from src.modules.workshops.application.create import (
    CreateWorkshopRequest,
    UpdateWorkshopRequest,
    WorkshopDTO,
    WorkshopListDTO,
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
            body: CreateWorkshopRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.create(body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get("", response_model=CoreResponse[WorkshopListDTO])
        async def list_workshops(
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            query: str | None = None,
            certified_only: bool = False,
            offset: int = 0,
            limit: int = 100,
        ):
            result = await service.list(
                query=query, certified_only=certified_only, offset=offset, limit=limit
            )
            handle_service_result(result, response)
            return result

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
            body: UpdateWorkshopRequest,
            response: Response,
            service: WorkshopService = Depends(get_workshop_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.update(id, body, user_id)
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
