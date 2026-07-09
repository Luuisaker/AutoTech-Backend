from typing import Type
from uuid import UUID
from datetime import datetime, timezone
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.services.infrastructure.mapper import ServiceMapper
from src.modules.services.application.create import (
    CreateServiceRequest,
    UpdateServiceRequest,
    ServiceDTO,
    ServiceListDTO,
    ServiceWithWorkshopDTO,
    ServiceWithWorkshopListDTO,
    CreateServiceOrderRequest,
    SetQuoteRequest,
    UpdateServiceOrderStatusRequest,
    AddExtraChargeRequest,
    MarkServiceShippedRequest,
    RateServiceOrderRequest,
    ServiceOrderDTO,
    ServiceOrderRatingInfo,
    ServiceOrderListDTO,
)
from src.modules.services.domain.entity import Service
from src.modules.services.infrastructure.repository import (
    ServiceRepository,
    ServiceOrderRepository,
)
from src.modules.workshops.infrastructure.repository import WorkshopRepository
from src.config.models import ServiceOrder as ServiceOrderModel


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

        entity = Service(
            workshop_id=dto.workshop_id,
            service_name=dto.service_name,
            service_type=dto.service_type,
            standard_price_min=dto.standard_price_min,
            standard_price_max=dto.standard_price_max,
            vehicle_type=dto.vehicle_type or "ALL",
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
        service_type: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Response:
        async with self._transaction(service=ServiceRepository) as t:
            services = await t.service.search(
                query=query,
                min_price=min_price,
                max_price=max_price,
                certified_only=certified_only,
                service_type=service_type,
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

    async def search_with_workshops(
        self,
        query: str | None = None,
        service_type: str | None = None,
        certified_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Response:
        async with self._transaction(service=ServiceRepository) as t:
            rows = await t.service.search_with_workshop(
                query=query,
                service_type=service_type,
                certified_only=certified_only,
                offset=offset,
                limit=limit,
            )

        services: list[ServiceWithWorkshopDTO] = []
        for row in rows:
            model = row[0]
            dto = ServiceWithWorkshopDTO(
                id=model.id,
                workshop_id=model.workshop_id,
                service_name=model.service_name,
                service_type=model.service_type,
                standard_price_min=model.standard_price_min,
                standard_price_max=model.standard_price_max,
                vehicle_type=model.vehicle_type,
                created_at=model.created_at,
                workshop_name=row.workshop_name if hasattr(row, "workshop_name") else None,
                workshop_address=row.workshop_address if hasattr(row, "workshop_address") else None,
                workshop_photo_url=row.workshop_photo_url if hasattr(row, "workshop_photo_url") else None,
                workshop_certified=bool(row.workshop_certified) if hasattr(row, "workshop_certified") else None,
            )
            services.append(dto)

        return Response(
            status_code=200,
            success=True,
            content=ServiceWithWorkshopListDTO(services=services),
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
            if dto.service_type is not None:
                model.service_type = dto.service_type
            if dto.standard_price_min is not None:
                model.standard_price_min = dto.standard_price_min
            if dto.standard_price_max is not None:
                model.standard_price_max = dto.standard_price_max
            if dto.vehicle_type is not None:
                model.vehicle_type = dto.vehicle_type

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

    # -- Service Orders --

    async def create_service_order(
        self, dto: CreateServiceOrderRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
            service=ServiceRepository,
        ) as t:
            w_model = await t.workshop.get(str(dto.workshop_id))
            if not w_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Taller no encontrado",
                )

            s_model = await t.service.get(str(dto.service_id))
            if not s_model or s_model.workshop_id != dto.workshop_id:
                return Response(
                    status_code=404,
                    success=False,
                    message="Servicio no encontrado en este taller",
                )

            base_price = dto.base_price if dto.base_price is not None else s_model.standard_price_min

            so_model = ServiceOrderModel(
                user_id=user_id,
                workshop_id=dto.workshop_id,
                service_id=dto.service_id,
                vehicle_id=dto.vehicle_id,
                base_price=base_price,
                price_min=s_model.standard_price_min,
                price_max=s_model.standard_price_max,
                notes=dto.notes,
                status="PENDING",
            )
            so_model = await t.service_order.add(so_model)

            # Eagerly load relationships
            stmt = (
                select(ServiceOrderModel)
                .where(ServiceOrderModel.id == so_model.id)
                .options(
                    selectinload(ServiceOrderModel.workshop_service),
                    selectinload(ServiceOrderModel.workshop),
                    selectinload(ServiceOrderModel.vehicle),
                    selectinload(ServiceOrderModel.user),
                )
            )
            r = await t.service_order._session.execute(stmt)
            so_model = r.scalars().first()

            return Response(
                status_code=201,
                success=True,
                message="Orden de servicio creada exitosamente",
                content=self._build_service_order_dto(so_model),
            )

    async def get_service_order(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden de servicio no encontrada",
                )

            w_model = await t.workshop.get(str(so_model.workshop_id))
            is_owner = w_model and w_model.owner_id == user_id
            if so_model.user_id != user_id and not is_owner:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a esta orden",
                )

            return Response(
                status_code=200,
                success=True,
                content=self._build_service_order_dto(so_model),
            )

    async def mark_at_workshop(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.status != "PENDING":
                return Response(status_code=400, success=False, message="La orden no está pendiente")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            so_model.status = "AT_WORKSHOP"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Vehículo marcado como recibido en el taller", content=self._build_service_order_dto(so_model))

    async def set_quote(self, order_id: UUID, dto: SetQuoteRequest, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
            service=ServiceRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.status not in ("AT_WORKSHOP", "QUOTED"):
                return Response(status_code=400, success=False, message="La orden no está en estado válido para presupuestar")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            pmax = so_model.price_max or (so_model.workshop_service.standard_price_max if so_model.workshop_service else 0)
            pmin = so_model.price_min or (so_model.workshop_service.standard_price_min if so_model.workshop_service else 0)
            if dto.final_price < pmin or dto.final_price > pmax:
                return Response(status_code=400, success=False, message=f"El precio debe estar entre ${pmin:.2f} y ${pmax:.2f}")
            so_model.final_price = dto.final_price
            if dto.notes is not None:
                so_model.notes = dto.notes
            so_model.status = "QUOTED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Presupuesto enviado al cliente", content=self._build_service_order_dto(so_model))

    async def accept_quote(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "QUOTED":
                return Response(status_code=400, success=False, message="No hay presupuesto pendiente por aceptar")
            so_model.status = "ACCEPTED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Presupuesto aceptado", content=self._build_service_order_dto(so_model))

    async def reject_quote(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "QUOTED":
                return Response(status_code=400, success=False, message="No hay presupuesto pendiente por rechazar")
            so_model.status = "REJECTED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Presupuesto rechazado", content=self._build_service_order_dto(so_model))

    async def mark_delivered(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            if so_model.status != "COMPLETED":
                return Response(status_code=400, success=False, message="El servicio debe estar completado antes de entregar")
            so_model.status = "DELIVERED"
            so_model.delivered_at = datetime.now(timezone.utc)
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Vehículo entregado, orden cerrada", content=self._build_service_order_dto(so_model))

    async def list_my_service_orders(self, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            orders = await t.service_order.list_by_user(str(user_id))
            return Response(
                status_code=200,
                success=True,
                content=ServiceOrderListDTO(
                    service_orders=[self._build_service_order_dto(o) for o in orders]
                ),
            )

    async def list_workshop_service_orders(
        self, workshop_id: UUID, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            w_model = await t.workshop.get(str(workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            orders = await t.service_order.list_by_workshop(str(workshop_id))
            return Response(
                status_code=200,
                success=True,
                content=ServiceOrderListDTO(
                    service_orders=[self._build_service_order_dto(o) for o in orders]
                ),
            )

    async def update_service_order_status(
        self, order_id: UUID, dto: UpdateServiceOrderStatusRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden de servicio no encontrada",
                )

            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño del taller",
                )

            if dto.status == "COMPLETED":
                so_model.completed_at = datetime.now(timezone.utc)

            so_model.status = dto.status
            await t.service_order.update(so_model)

            return Response(
                status_code=200,
                success=True,
                message=f"Estado actualizado a {dto.status}",
                content=self._build_service_order_dto(so_model),
            )

    async def add_extra_charge(
        self, order_id: UUID, dto: AddExtraChargeRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden de servicio no encontrada",
                )

            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño del taller",
                )

            so_model.extra_charge = dto.extra_charge
            so_model.extra_charge_note = dto.extra_charge_note
            so_model.extra_charge_status = "PENDING_APPROVAL"
            await t.service_order.update(so_model)

            return Response(
                status_code=200,
                success=True,
                message="Cargo extra agregado, pendiente de aprobación",
                content=self._build_service_order_dto(so_model),
            )

    async def mark_service_shipped(self, order_id: UUID, user_id: UUID, dto: MarkServiceShippedRequest) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            if so_model.status != "COMPLETED":
                return Response(status_code=400, success=False, message="El servicio debe estar completado antes de enviar")
            if so_model.delivery_method != "SHIPPING":
                return Response(status_code=400, success=False, message="Esta orden no es para envío")
            so_model.status = "SHIPPED"
            so_model.tracking_number = dto.tracking_number
            so_model.shipping_notes = dto.shipping_notes
            so_model.shipped_at = datetime.now(timezone.utc)
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Orden marcada como enviada", content=self._build_service_order_dto(so_model))

    async def mark_service_received(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No eres el comprador de esta orden")
            if so_model.status != "SHIPPED":
                return Response(status_code=400, success=False, message="La orden no está en estado enviado")
            so_model.status = "DELIVERED"
            so_model.delivered_at = datetime.now(timezone.utc)
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Recepción confirmada", content=self._build_service_order_dto(so_model))

    async def cancel_service_order(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "PENDING":
                return Response(status_code=400, success=False, message="Solo se pueden cancelar órdenes pendientes")
            so_model.status = "CANCELLED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Orden cancelada exitosamente", content=self._build_service_order_dto(so_model))

    async def close_service_as_client(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No eres el comprador de esta orden")
            if so_model.status != "DELIVERED":
                return Response(status_code=400, success=False, message="La orden debe estar entregada para cerrar")
            so_model.closed_by_client = 1
            if so_model.closed_by_workshop:
                so_model.status = "CLOSED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Orden cerrada", content=self._build_service_order_dto(so_model))

    async def close_service_as_workshop(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            if so_model.status != "DELIVERED":
                return Response(status_code=400, success=False, message="La orden debe estar entregada para cerrar")
            so_model.closed_by_workshop = 1
            if so_model.closed_by_client:
                so_model.status = "CLOSED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Orden cerrada por el taller", content=self._build_service_order_dto(so_model))

    async def rate_service_order_workshop(self, order_id: UUID, user_id: UUID, dto: RateServiceOrderRequest) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No eres el comprador de esta orden")
            if so_model.status != "CLOSED":
                return Response(status_code=400, success=False, message="La orden debe estar cerrada para calificar")
            if so_model.client_rating is not None:
                return Response(status_code=400, success=False, message="Ya calificaste esta orden")
            so_model.client_rating = dto.rating
            so_model.client_review = dto.comment
            await t.service_order.update(so_model)
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if w_model:
                all_so_ratings = select(ServiceOrderModel.client_rating).where(
                    ServiceOrderModel.workshop_id == so_model.workshop_id,
                    ServiceOrderModel.client_rating.isnot(None),
                )
                r = await t.service_order._session.execute(all_so_ratings)
                ratings = [row[0] for row in r if row[0] is not None]
                if ratings:
                    avg = sum(ratings) / len(ratings)
                    w_model.average_rating = round(avg, 1)
                    await t.workshop.update(w_model)
            return Response(status_code=200, success=True, message="Taller calificado exitosamente", content=self._build_service_order_dto(so_model))

    async def rate_service_order_client(self, order_id: UUID, user_id: UUID, dto: RateServiceOrderRequest) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            if so_model.status != "CLOSED":
                return Response(status_code=400, success=False, message="La orden debe estar cerrada para calificar")
            if so_model.workshop_rating is not None:
                return Response(status_code=400, success=False, message="Ya calificaste esta orden")
            so_model.workshop_rating = dto.rating
            so_model.workshop_review = dto.comment
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Cliente calificado exitosamente", content=self._build_service_order_dto(so_model))

    async def approve_extra_charge(
        self, order_id: UUID, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden de servicio no encontrada",
                )

            if so_model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a esta orden",
                )

            if so_model.extra_charge_status != "PENDING_APPROVAL":
                return Response(
                    status_code=400,
                    success=False,
                    message="No hay cargo extra pendiente por aprobar",
                )

            so_model.extra_charge_status = "APPROVED"
            await t.service_order.update(so_model)

            return Response(
                status_code=200,
                success=True,
                message="Cargo extra aprobado",
                content=self._build_service_order_dto(so_model),
            )

    async def reject_extra_charge(
        self, order_id: UUID, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
        ) as t:
            so_model = await t.service_order.get(str(order_id))
            if not so_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden de servicio no encontrada",
                )

            if so_model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a esta orden",
                )

            if so_model.extra_charge_status != "PENDING_APPROVAL":
                return Response(
                    status_code=400,
                    success=False,
                    message="No hay cargo extra pendiente por rechazar",
                )

            so_model.extra_charge_status = "REJECTED"
            so_model.extra_charge = 0.0
            await t.service_order.update(so_model)

            return Response(
                status_code=200,
                success=True,
                message="Cargo extra rechazado",
                content=self._build_service_order_dto(so_model),
            )

    def _build_service_order_dto(self, o: ServiceOrderModel) -> ServiceOrderDTO:
        extra = o.extra_charge if o.extra_charge_status == "APPROVED" else 0.0
        final_price = o.final_price if o.final_price is not None else (o.base_price + extra)
        return ServiceOrderDTO(
            id=o.id,
            user_id=o.user_id,
            workshop_id=o.workshop_id,
            service_id=o.service_id,
            vehicle_id=o.vehicle_id,
            service_name=o.workshop_service.service_name if o.workshop_service else "",
            workshop_name=o.workshop.name if o.workshop else None,
            vehicle_brand=o.vehicle.brand if o.vehicle else "",
            vehicle_model=o.vehicle.model if o.vehicle else "",
            vehicle_license_plate=o.vehicle.license_plate if o.vehicle else "",
            user_first_name=o.user.first_name if o.user else "",
            user_last_name=o.user.last_name if o.user else "",
            status=o.status,
            base_price=o.base_price,
            final_price=final_price,
            extra_charge=o.extra_charge,
            extra_charge_note=o.extra_charge_note,
            extra_charge_status=o.extra_charge_status,
            price_min=o.price_min or (o.workshop_service.standard_price_min if o.workshop_service else 0.0),
            price_max=o.price_max or (o.workshop_service.standard_price_max if o.workshop_service else 0.0),
            notes=o.notes,
            delivery_method=o.delivery_method,
            tracking_number=o.tracking_number,
            shipping_notes=o.shipping_notes,
            shipped_at=o.shipped_at,
            closed_by_client=bool(o.closed_by_client),
            closed_by_workshop=bool(o.closed_by_workshop),
            created_at=o.created_at,
            completed_at=o.completed_at,
            delivered_at=o.delivered_at,
            ratings=ServiceOrderRatingInfo(
                client_rating=o.client_rating,
                client_rated=o.client_rating is not None,
                workshop_rating=o.workshop_rating,
                workshop_rated=o.workshop_rating is not None,
            ),
        )


def get_service_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> ServiceService:
    return ServiceService(transaction)
