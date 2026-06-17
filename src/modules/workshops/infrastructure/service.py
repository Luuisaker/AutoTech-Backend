from typing import Type
from uuid import UUID
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.workshops.infrastructure.mapper import WorkshopMapper
from src.modules.workshops.application.create import (
    CreateWorkshopRequest,
    UpdateWorkshopRequest,
    WorkshopDTO,
    WorkshopListDTO,
)
from src.modules.workshops.domain.entity import Workshop
from src.modules.workshops.infrastructure.repository import WorkshopRepository
from src.modules.users.infrastructure.repository import UserRepository


class WorkshopService:
    __mapper = WorkshopMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    async def create(self, dto: CreateWorkshopRequest, owner_id: UUID) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
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
                verification_document_url=dto.verification_document_url,
            )

            w_model = await t.workshop.add(self.__mapper.to_model(workshop_entity))

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
        offset: int = 0,
        limit: int = 100,
    ) -> Response:
        async with self._transaction(workshop=WorkshopRepository) as t:
            workshops = await t.workshop.search(
                query=query, certified_only=certified_only, offset=offset, limit=limit
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
        self, workshop_id: UUID, dto: UpdateWorkshopRequest, owner_id: UUID
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
        if dto.verification_document_url is not None:
            w_model.verification_document_url = dto.verification_document_url

        async with self._transaction(workshop=WorkshopRepository) as t:
            w_model = await t.workshop.update(w_model)

        return Response(
            status_code=200,
            success=True,
            message="Taller actualizado exitosamente",
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
            if owner and owner.role != "ADMIN":
                owner.role = "WORKSHOP_OWNER"
                await t.user.update(owner)

        return Response(
            status_code=200,
            success=True,
            message="Taller certificado exitosamente",
            content=WorkshopDTO.model_validate(self.__mapper.to_entity(w_model)),
        )


def get_workshop_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> WorkshopService:
    return WorkshopService(transaction)
