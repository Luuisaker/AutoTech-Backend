from typing import Type
from uuid import UUID
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.vehicles.infrastructure.mapper import VehicleMapper
from src.modules.vehicles.application.create import (
    CreateVehicleRequest,
    UpdateVehicleRequest,
    VehicleDTO,
    VehicleListDTO,
    VehicleTypeListDTO,
)
from src.modules.vehicles.domain.entity import Vehicle
from src.modules.vehicles.domain.types import VehicleType
from src.modules.vehicles.infrastructure.repository import VehicleRepository


class VehicleService:
    __mapper = VehicleMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    @staticmethod
    def get_types() -> Response:
        return Response(
            status_code=200,
            success=True,
            content=VehicleTypeListDTO(types=[v.value for v in VehicleType]),
        )

    async def create(self, dto: CreateVehicleRequest, owner_id: UUID) -> Response:
        async with self._transaction(vehicle=VehicleRepository) as t:
            if await t.vehicle.get_by_license_plate(dto.license_plate):
                return Response(
                    status_code=400,
                    success=False,
                    message="La placa ya está registrada",
                )

            if await t.vehicle.get_by_vin(dto.vin):
                return Response(
                    status_code=400,
                    success=False,
                    message="El VIN ya está registrado",
                )

            vehicle_entity = Vehicle(
                owner_id=owner_id,
                vehicle_type=dto.vehicle_type,
                brand=dto.brand,
                model=dto.model,
                year=dto.year,
                license_plate=dto.license_plate,
                vin=dto.vin,
            )

            v_model = await t.vehicle.add(self.__mapper.to_model(vehicle_entity))

        return Response(
            status_code=201,
            success=True,
            message="Vehículo registrado exitosamente",
            content=VehicleDTO.model_validate(self.__mapper.to_entity(v_model)),
        )

    async def list_by_owner(self, owner_id: UUID) -> Response:
        async with self._transaction(vehicle=VehicleRepository) as t:
            vehicles = await t.vehicle.list_by_owner(str(owner_id))

        return Response(
            status_code=200,
            success=True,
            content=VehicleListDTO(
                vehicles=[
                    VehicleDTO.model_validate(self.__mapper.to_entity(v))
                    for v in vehicles
                ]
            ),
        )

    async def get_by_id(self, vehicle_id: UUID, owner_id: UUID) -> Response:
        async with self._transaction(vehicle=VehicleRepository) as t:
            v_model = await t.vehicle.get(str(vehicle_id))

        if not v_model:
            return Response(
                status_code=404,
                success=False,
                message="Vehículo no encontrado",
            )

        if v_model.owner_id != owner_id:
            return Response(
                status_code=403,
                success=False,
                message="No tienes acceso a este vehículo",
            )

        return Response(
            status_code=200,
            success=True,
            content=VehicleDTO.model_validate(self.__mapper.to_entity(v_model)),
        )

    async def update(
        self, vehicle_id: UUID, dto: UpdateVehicleRequest | None = None, owner_id: UUID | None = None, *, photo_url: str | None = None
    ) -> Response:
        async with self._transaction(vehicle=VehicleRepository) as t:
            v_model = await t.vehicle.get(str(vehicle_id))

        if not v_model:
            return Response(
                status_code=404,
                success=False,
                message="Vehículo no encontrado",
            )

        if v_model.owner_id != owner_id:
            return Response(
                status_code=403,
                success=False,
                message="No tienes acceso a este vehículo",
            )

        if photo_url is not None:
            v_model.photo_url = photo_url

        if dto is not None:
            if dto.vehicle_type is not None:
                v_model.vehicle_type = dto.vehicle_type
            if dto.brand is not None:
                v_model.brand = dto.brand
            if dto.model is not None:
                v_model.model = dto.model
            if dto.year is not None:
                v_model.year = dto.year

        async with self._transaction(vehicle=VehicleRepository) as t:
            v_model = await t.vehicle.update(v_model)

        return Response(
            status_code=200,
            success=True,
            message="Vehículo actualizado exitosamente",
            content=VehicleDTO.model_validate(self.__mapper.to_entity(v_model)),
        )

    async def deactivate(self, vehicle_id: UUID, owner_id: UUID) -> Response:
        async with self._transaction(vehicle=VehicleRepository) as t:
            v_model = await t.vehicle.get(str(vehicle_id))

        if not v_model:
            return Response(
                status_code=404,
                success=False,
                message="Vehículo no encontrado",
            )

        if v_model.owner_id != owner_id:
            return Response(
                status_code=403,
                success=False,
                message="No tienes acceso a este vehículo",
            )

        v_model.is_active = 0

        async with self._transaction(vehicle=VehicleRepository) as t:
            await t.vehicle.update(v_model)

        return Response(
            status_code=200,
            success=True,
            message="Vehículo eliminado exitosamente",
        )


def get_vehicle_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> VehicleService:
    return VehicleService(transaction)
