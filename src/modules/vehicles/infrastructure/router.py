from uuid import UUID
from fastapi import Depends, APIRouter, Response
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.modules.vehicles.infrastructure.service import (
    VehicleService,
    get_vehicle_service,
)
from src.modules.users.infrastructure.auth import get_current_user_id
from src.utils.handle_service_result import handle_service_result
from src.modules.vehicles.application.create import (
    CreateVehicleRequest,
    UpdateVehicleRequest,
    VehicleDTO,
    VehicleListDTO,
    VehicleTypeListDTO,
)


class VehicleRouter(BaseRouter):
    __prefix__ = "/vehicles"
    __tag__ = "Vehicles"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.get("/types", response_model=CoreResponse[VehicleTypeListDTO])
        async def vehicle_types():
            return VehicleService.get_types()

        @self._router.post("", response_model=CoreResponse[VehicleDTO], status_code=201)
        async def create(
            body: CreateVehicleRequest,
            response: Response,
            service: VehicleService = Depends(get_vehicle_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.create(body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.get("", response_model=CoreResponse[VehicleListDTO])
        async def list_vehicles(
            response: Response,
            service: VehicleService = Depends(get_vehicle_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.list_by_owner(user_id)
            handle_service_result(result, response)
            return result

        @self._router.get("/{id}", response_model=CoreResponse[VehicleDTO])
        async def get_vehicle(
            id: UUID,
            response: Response,
            service: VehicleService = Depends(get_vehicle_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.get_by_id(id, user_id)
            handle_service_result(result, response)
            return result

        @self._router.put("/{id}", response_model=CoreResponse[VehicleDTO])
        async def update_vehicle(
            id: UUID,
            body: UpdateVehicleRequest,
            response: Response,
            service: VehicleService = Depends(get_vehicle_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.update(id, body, user_id)
            handle_service_result(result, response)
            return result

        @self._router.delete("/{id}", response_model=CoreResponse, status_code=200)
        async def delete_vehicle(
            id: UUID,
            response: Response,
            service: VehicleService = Depends(get_vehicle_service),
            user_id: UUID = Depends(get_current_user_id),
        ):
            result = await service.deactivate(id, user_id)
            handle_service_result(result, response)
            return result
