from typing import Type
from uuid import UUID
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.services.infrastructure.mapper import ServiceMapper
from src.modules.services.application.create import (
    CreateServiceRequest,
    UpdateServiceRequest,
    ServiceDTO,
    ServiceListDTO,
)
from src.modules.services.domain.entity import Service
from src.modules.services.infrastructure.repository import ServiceRepository
from src.modules.workshops.infrastructure.repository import WorkshopRepository


class ServiceService:
    __mapper = ServiceMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    async def create(self, dto: CreateServiceRequest, user_id: UUID) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.get(str(dto.workshop_id))

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

            if not w_model.is_certified:
                return Response(
                    status_code=403,
                    success=False,
                    message="El taller debe estar certificado para publicar servicios",
                )

        entity = Service(
            workshop_id=dto.workshop_id,
            service_name=dto.service_name,
            standard_price_min=dto.standard_price_min,
            standard_price_max=dto.standard_price_max,
        )

        async with self._transaction(service=ServiceRepository) as t:
            model = await t.service.add(self.__mapper.to_model(entity))

        return Response(
            status_code=201,
            success=True,
            message="Servicio creado exitosamente",
            content=ServiceDTO.model_validate(self.__mapper.to_entity(model)),
        )

    async def list_by_workshop(self, workshop_id: UUID) -> Response:
        async with self._transaction(service=ServiceRepository) as t:
            services = await t.service.list_by_workshop(str(workshop_id))

        return Response(
            status_code=200,
            success=True,
            content=ServiceListDTO(
                services=[
                    ServiceDTO.model_validate(self.__mapper.to_entity(s))
                    for s in services
                ]
            ),
        )

    async def search(
        self,
        query: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        certified_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Response:
        async with self._transaction(service=ServiceRepository) as t:
            services = await t.service.search(
                query=query,
                min_price=min_price,
                max_price=max_price,
                certified_only=certified_only,
                offset=offset,
                limit=limit,
            )

        return Response(
            status_code=200,
            success=True,
            content=ServiceListDTO(
                services=[
                    ServiceDTO.model_validate(self.__mapper.to_entity(s))
                    for s in services
                ]
            ),
        )

    async def get_by_id(self, service_id: UUID) -> Response:
        async with self._transaction(service=ServiceRepository) as t:
            model = await t.service.get(str(service_id))

        if not model:
            return Response(
                status_code=404,
                success=False,
                message="Servicio no encontrado",
            )

        return Response(
            status_code=200,
            success=True,
            content=ServiceDTO.model_validate(self.__mapper.to_entity(model)),
        )

    async def update(
        self, service_id: UUID, dto: UpdateServiceRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service=ServiceRepository, workshop=WorkshopRepository
        ) as t:
            model = await t.service.get(str(service_id))

            if not model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Servicio no encontrado",
                )

            w_model = await t.workshop.get(str(model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            if dto.service_name is not None:
                model.service_name = dto.service_name
            if dto.standard_price_min is not None:
                model.standard_price_min = dto.standard_price_min
            if dto.standard_price_max is not None:
                model.standard_price_max = dto.standard_price_max

            model = await t.service.update(model)

        return Response(
            status_code=200,
            success=True,
            message="Servicio actualizado exitosamente",
            content=ServiceDTO.model_validate(self.__mapper.to_entity(model)),
        )

    async def delete(self, service_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service=ServiceRepository, workshop=WorkshopRepository
        ) as t:
            model = await t.service.get(str(service_id))

            if not model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Servicio no encontrado",
                )

            w_model = await t.workshop.get(str(model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            await t.service.delete(model)

        return Response(
            status_code=200,
            success=True,
            message="Servicio eliminado exitosamente",
        )


def get_service_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> ServiceService:
    return ServiceService(transaction)
