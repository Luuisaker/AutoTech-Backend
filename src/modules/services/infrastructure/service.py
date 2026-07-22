from typing import Type, Any
from uuid import UUID
from datetime import datetime, timezone
from fastapi import Depends
from sqlalchemy import select, update as sql_update
from sqlalchemy.orm import selectinload

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID
from src.modules.services.infrastructure.mapper import ServiceMapper
from src.modules.users.infrastructure.repository import UserRepository
from src.modules.services.application.create import (
    CreateServiceRequest,
    UpdateServiceRequest,
    ServiceDTO,
    ServiceListDTO,
    ServiceWithWorkshopDTO,
    ServiceWithWorkshopListDTO,
    CreateServiceOrderRequest,
    SetQuoteRequest,
    SetRevisionRequest,
    UpdateServiceOrderStatusRequest,
    AddExtraChargeRequest,
    MarkServiceShippedRequest,
    RateServiceOrderRequest,
    PayServiceOrderRequest,
    MarkServiceInstallmentPaidRequest,
    ServiceOrderDTO,
    ServiceOrderRatingInfo,
    ServiceOrderPaymentDTO,
    ServiceOrderInstallmentDTO,
    ServiceOrderListDTO,
    AdminServiceOrderDetailDTO,
)
from src.modules.services.domain.entity import Service
from src.modules.services.infrastructure.repository import (
    ServiceRepository,
    ServiceOrderRepository,
    ServiceOrderPaymentRepository,
)
from src.modules.workshops.infrastructure.repository import WorkshopRepository
from src.config.models import ServiceOrder as ServiceOrderModel
from src.config.models import UserRole as UserRoleModel
from src.config.models import ServiceOrderPayment as ServiceOrderPaymentModel
from src.config.models import ServiceOrderInstallment as ServiceOrderInstallmentModel
from src.config.models import WorkshopCommission as WorkshopCommissionModel
from src.config.models import User as UserModel
from src.config.models import OrderReview as OrderReviewModel
from src.config.models import Order as OrderModel
from src.modules.credit.infrastructure.repository import CreditLevelRepository, CreditHistoryRepository, LateFeeRepository
from src.modules.credit.infrastructure.service import CreditService


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
            revision_cost_min=dto.revision_cost_min,
            revision_cost_max=dto.revision_cost_max,
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
        workshop_id: UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Response:
        async with self._transaction(service=ServiceRepository) as t:
            rows = await t.service.search_with_workshop(
                query=query,
                service_type=service_type,
                certified_only=certified_only,
                workshop_id=workshop_id,
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
            if dto.revision_cost_min is not None:
                model.revision_cost_min = dto.revision_cost_min
            if dto.revision_cost_max is not None:
                model.revision_cost_max = dto.revision_cost_max
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

            model.deleted_at = datetime.now(timezone.utc)
            await t.service.update(model)

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
            # Block service order if user has any open mora
            late_fee_repo = LateFeeRepository(t.service_order._session)
            open_moras = await late_fee_repo.list_open_by_user(user_id)
            if open_moras:
                return Response(
                    status_code=400,
                    success=False,
                    message="Tienes moras pendientes. Paga primero las moras antes de solicitar servicios.",
                )

            w_model = await t.workshop.get(str(dto.workshop_id))
            if not w_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Taller no encontrado",
                )

            if w_model.is_suspended:
                return Response(
                    status_code=400,
                    success=False,
                    message="El taller está fuera de servicio",
                )

            if w_model.commission_suspended:
                return Response(
                    status_code=403,
                    success=False,
                    message="El taller tiene comisiones impagas y está suspendido temporalmente.",
                )

            # Check for late commissions (pending commissions from previous months)
            now = datetime.now(timezone.utc)
            current_month = now.month
            current_year = now.year
            late_comm_stmt = select(WorkshopCommissionModel).where(
                WorkshopCommissionModel.workshop_id == dto.workshop_id,
                WorkshopCommissionModel.status == "PENDING",
            )
            late_comm_r = await t.service_order._session.execute(late_comm_stmt)
            late_comms = late_comm_r.scalars().all()
            has_late = any(
                c.period_year < current_year or (c.period_year == current_year and c.period_month < current_month)
                for c in late_comms
            )
            if has_late:
                return Response(
                    status_code=400,
                    success=False,
                    message="El taller tiene comisiones atrasadas pendientes. El financiamiento está pausado hasta que las pague.",
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
                revision=s_model.revision_cost_min,
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
                    selectinload(ServiceOrderModel.payments),
                    selectinload(ServiceOrderModel.installments),
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

            is_admin = False
            if so_model.user_id != user_id and not is_owner:
                stmt = select(UserRoleModel).where(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id.in_([ROLE_NAME_TO_UUID["ADMIN"], ROLE_NAME_TO_UUID["SUPERADMIN"]]),
                )
                r = await t.service_order._session.execute(stmt)
                is_admin = r.scalars().first() is not None

            if so_model.user_id != user_id and not is_owner and not is_admin:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a esta orden",
                )

            late_fees_map = await self._load_late_fees_map(
                t.service_order._session, so_model.installments or []
            )
            dto = self._build_service_order_dto(so_model, late_fees_map)

            owner = None
            if w_model and w_model.owner_id:
                from src.config.models import User

                owner = await t.workshop._session.get(User, w_model.owner_id)

            dto.owner_first_name = owner.first_name if owner else None
            dto.owner_last_name = owner.last_name if owner else None
            dto.owner_ci = owner.ci if owner else None
            dto.owner_email = owner.email if owner else None

            return Response(
                status_code=200,
                success=True,
                content=dto,
            )

    async def admin_get_service_order(self, order_id: UUID) -> Response:
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
            owner = None
            if w_model and w_model.owner_id:
                owner = await t.workshop._session.get(
                    __import__(
                        "src.config.models", fromlist=["User"]
                    ).User,
                    w_model.owner_id,
                )

            late_fees_map = await self._load_late_fees_map(
                t.service_order._session, so_model.installments or []
            )
            dto = self._build_service_order_dto(so_model, late_fees_map)
            if owner:
                dto.owner_first_name = owner.first_name
                dto.owner_last_name = owner.last_name
                dto.owner_email = owner.email
                dto.owner_ci = owner.ci
            return Response(
                status_code=200,
                success=True,
                content=AdminServiceOrderDetailDTO(**dto.model_dump()),
            )

    async def mark_at_workshop(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.status not in ("PENDING", "DROPPED_OFF"):
                return Response(status_code=400, success=False, message="La orden no está pendiente de recepción")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            so_model.status = "AT_WORKSHOP"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Vehículo marcado como recibido en el taller", content=self._build_service_order_dto(so_model))

    async def mark_dropped_off(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No eres el comprador de esta orden")
            if so_model.status != "PENDING":
                return Response(status_code=400, success=False, message="La orden no está pendiente")
            so_model.status = "DROPPED_OFF"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Vehículo marcado como entregado en el taller", content=self._build_service_order_dto(so_model))

    async def set_revision(self, order_id: UUID, dto: SetRevisionRequest, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.status != "AT_WORKSHOP":
                return Response(status_code=400, success=False, message="La orden no está en el taller")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            rmin = so_model.workshop_service.revision_cost_min or 0
            rmax = so_model.workshop_service.revision_cost_max or 0
            if dto.revision_cost < rmin or dto.revision_cost > rmax:
                return Response(
                    status_code=400,
                    success=False,
                    message=f"El costo de revisión debe estar entre ${rmin:.2f} y ${rmax:.2f}",
                )
            so_model.revision = dto.revision_cost
            so_model.status = "REVISION_SENT"
            await t.service_order.update(so_model)
            _result = Response(status_code=200, success=True, message="Costo de revisión enviado al cliente", content=self._build_service_order_dto(so_model))

        # Send revision sent email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import service_revision_sent
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, Workshop as _WM, WorkshopService as _WSM, ServiceOrder as _SOM
            async with _gs() as _sess:
                _so = await _sess.get(_SOM, order_id)
                if _so:
                    _u = await _sess.get(_UM, _so.user_id)
                    _w = await _sess.get(_WM, _so.workshop_id)
                    _ws = await _sess.get(_WSM, _so.workshop_service_id) if _so.workshop_service_id else None
                    _svc_name = _ws.name if _ws else "Servicio"
                    _ws_name = _w.name if _w else "AutoTech"
                    if _u:
                        await send_email(
                            _u.email,
                            "Revisión enviada - AutoTech",
                            service_revision_sent(
                                buyer_name=_u.first_name,
                                service_name=_svc_name,
                                workshop_name=_ws_name,
                                revision_cost=dto.revision_cost,
                                order_id=str(order_id),
                                lang=_u.language_preference or "es",
                            ),
                        )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send service revision sent email: {e}", exc_info=True)

        return _result

    async def accept_revision(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "REVISION_SENT":
                return Response(status_code=400, success=False, message="No hay revisión pendiente por aceptar")
            so_model.status = "AT_WORKSHOP"
            so_model.revision = so_model.revision or 0
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Revisión aceptada", content=self._build_service_order_dto(so_model))

    async def reject_revision(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "REVISION_SENT":
                return Response(status_code=400, success=False, message="No hay revisión pendiente por rechazar")
            so_model.status = "CANCELLED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Revisión rechazada, orden cancelada", content=self._build_service_order_dto(so_model))

    async def set_quote(self, order_id: UUID, dto: SetQuoteRequest, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
            service=ServiceRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
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
            _result = Response(status_code=200, success=True, message="Presupuesto enviado al cliente", content=self._build_service_order_dto(so_model))

        # Send quote sent email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import service_quote_sent
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, Workshop as _WM, WorkshopService as _WSM, ServiceOrder as _SOM
            async with _gs() as _sess:
                _so = await _sess.get(_SOM, order_id)
                if _so:
                    _u = await _sess.get(_UM, _so.user_id)
                    _w = await _sess.get(_WM, _so.workshop_id)
                    _ws = await _sess.get(_WSM, _so.workshop_service_id) if _so.workshop_service_id else None
                    _svc_name = _ws.name if _ws else "Servicio"
                    _ws_name = _w.name if _w else "AutoTech"
                    _price = _so.final_price or _so.base_price
                    if _u:
                        await send_email(
                            _u.email,
                            "Presupuesto recibido - AutoTech",
                            service_quote_sent(
                                buyer_name=_u.first_name,
                                service_name=_svc_name,
                                workshop_name=_ws_name,
                                price=_price,
                                order_id=str(order_id),
                                lang=_u.language_preference or "es",
                            ),
                        )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send service quote sent email: {e}", exc_info=True)

        return _result

    async def accept_quote(self, order_id: UUID, user_id: UUID, dto: Any = None) -> Response:
        if dto and getattr(dto, 'is_financed', False):
            from src.modules.services.application.create import FinanceServiceOrderRequest
            finance_dto = FinanceServiceOrderRequest(
                down_payment_pct=dto.down_payment_pct or 0,
                payment_method=dto.payment_method or "OTHER",
                reference_number=dto.reference_number,
                rate=dto.rate,
                rate_date=dto.rate_date,
            )
            return await self.finance_service_order(order_id, finance_dto, user_id)

        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "QUOTED":
                return Response(status_code=400, success=False, message="No hay presupuesto pendiente por aceptar")
            so_model.status = "ACCEPTED"
            await t.service_order.update(so_model)

            # Create commission record for de contado service orders (5% of total)
            total_price = so_model.final_price or so_model.base_price
            if total_price and total_price > 0:
                now_dt = datetime.now(timezone.utc)
                commission_amount = round(total_price * 0.05, 2)
                commission = WorkshopCommissionModel(
                    workshop_id=so_model.workshop_id,
                    service_order_id=order_id,
                    financed_amount=total_price,
                    commission_rate=5.0,
                    commission_amount=commission_amount,
                    period_month=now_dt.month,
                    period_year=now_dt.year,
                    status="PENDING",
                )
                t.service_order._session.add(commission)
                await t.service_order._session.flush()

            return Response(status_code=200, success=True, message="Presupuesto aceptado", content=self._build_service_order_dto(so_model))

    async def reject_quote(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "QUOTED":
                return Response(status_code=400, success=False, message="No hay presupuesto pendiente por rechazar")
            so_model.status = "REJECTED"
            if so_model.revision and so_model.revision > 0:
                so_model.final_price = so_model.revision
            else:
                so_model.final_price = 0
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Presupuesto rechazado", content=self._build_service_order_dto(so_model))

    async def pay_service_order(
        self, order_id: UUID, dto: PayServiceOrderRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            service_order_payment=ServiceOrderPaymentRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status not in ("ACCEPTED", "REJECTED", "IN_PROGRESS"):
                return Response(status_code=400, success=False, message="La orden no está en estado válido para pago")

            if so_model.status == "REJECTED":
                total_owed = so_model.revision or 0.0
            else:
                extra = so_model.extra_charge if so_model.extra_charge_status == "APPROVED" else 0.0
                total_owed = (so_model.final_price or 0.0) + extra

            paid_sum = sum(
                p.amount for p in so_model.payments if p.status == "PAID"
            )
            remaining = max(0.0, total_owed - paid_sum)

            if remaining <= 0:
                return Response(status_code=400, success=False, message="No hay monto pendiente por pagar")

            effective_rate = dto.rate
            effective_rate_date = dto.rate_date
            if dto.paid_at:
                if effective_rate is None:
                    from src.modules.orders.infrastructure.bcv import get_bcv_rate_for_date
                    rate_info = await get_bcv_rate_for_date(dto.paid_at)
                    if rate_info:
                        effective_rate = rate_info.usd
                        effective_rate_date = rate_info.date

            payment = ServiceOrderPaymentModel(
                service_order_id=order_id,
                user_id=user_id,
                amount=remaining,
                payment_method=dto.payment_method,
                reference_number=dto.reference_number,
                status="PENDING_VERIFICATION",
                rate=effective_rate,
                rate_date=effective_rate_date,
                paid_at=dto.paid_at,
            )
            await t.service_order_payment.add(payment)

            return Response(status_code=201, success=True, message="Pago registrado, pendiente de verificación", content=self._build_service_order_dto(so_model))

    async def finance_service_order(
        self, order_id: UUID, dto, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            service_order_payment=ServiceOrderPaymentRepository,
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status != "QUOTED":
                return Response(status_code=400, success=False, message="No hay presupuesto pendiente por aceptar")

            total_price = so_model.final_price or so_model.base_price

            # Validate min down payment against user's credit level
            user_model = await t.user.get(str(user_id))
            if not user_model:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            level_model = await t.credit_level.get_by_level(user_model.credit_level)
            min_pct = level_model.min_down_payment_pct if level_model else 0
            if dto.down_payment_pct < min_pct:
                return Response(
                    status_code=400, success=False,
                    message=(
                        f"El pago inicial mínimo es {min_pct}% para tu nivel de crédito "
                        f"(nivel {user_model.credit_level})"
                    ),
                )

            # Block financing if user has open mora
            credit_svc = CreditService.__new__(CreditService)
            has_mora = await credit_svc.user_has_open_mora(user_id)
            if has_mora:
                return Response(
                    status_code=403, success=False,
                    message="Tienes moras pendientes. Paga las moras antes de financiar.",
                )

            # Block financing if workshop has unpaid commissions from previous months
            now_dt = datetime.now(timezone.utc)
            comm_stmt = select(WorkshopCommissionModel).where(
                WorkshopCommissionModel.workshop_id == so_model.workshop_id,
                WorkshopCommissionModel.status == "PENDING",
            )
            comm_stmt = comm_stmt.where(
                (WorkshopCommissionModel.period_year < now_dt.year) |
                (
                    (WorkshopCommissionModel.period_year == now_dt.year) &
                    (WorkshopCommissionModel.period_month < now_dt.month)
                )
            )
            r = await t.service_order._session.execute(comm_stmt)
            unpaid_commissions = r.scalars().all()
            if unpaid_commissions:
                total_debt = sum(c.commission_amount for c in unpaid_commissions)
                return Response(
                    status_code=403, success=False,
                    message=(
                        f"El taller tiene comisiones pendientes de ${total_debt:.2f} "
                        f"de meses anteriores. El financiamiento está pausado hasta que se regularice."
                    ),
                )

            # Calculate exact amounts in cents to ensure sum equals total_price
            total_cents = int(round(total_price * 100))
            down_cents = int(total_cents * dto.down_payment_pct // 100)
            financed_cents = total_cents - down_cents
            down_payment = down_cents / 100.0
            financed_amount = financed_cents / 100.0

            # Check credit eligibility — calculate debts dynamically
            from src.config.models import Installment as FinInst, Order as FinOrd
            from src.config.models import ServiceOrderInstallment as FinSOI, ServiceOrder as FinSO
            from sqlalchemy import func as sql_func, select as sql_select

            p_debt_stmt = (
                sql_select(sql_func.coalesce(sql_func.sum(FinInst.amount), 0.0))
                .join(FinOrd, FinInst.order_id == FinOrd.id)
                .where(
                    FinOrd.user_id == user_id,
                    FinInst.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    FinInst.deleted_at.is_(None),
                    FinOrd.deleted_at.is_(None),
                )
            )
            p_debt_r = await t.service_order._session.execute(p_debt_stmt)
            current_parts_debt = round(p_debt_r.scalar() or 0.0, 2)

            s_debt_stmt = (
                sql_select(sql_func.coalesce(sql_func.sum(FinSOI.amount), 0.0))
                .join(FinSO, FinSOI.service_order_id == FinSO.id)
                .where(
                    FinSO.user_id == user_id,
                    FinSOI.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                )
            )
            s_debt_r = await t.service_order._session.execute(s_debt_stmt)
            current_service_debt = round(s_debt_r.scalar() or 0.0, 2)

            service_available = user_model.service_credit_limit - current_service_debt
            parts_available = user_model.parts_credit_limit - current_parts_debt

            if financed_amount > service_available:
                # Check if parts line can cover the excess
                excess = financed_amount - service_available
                if excess > parts_available:
                    return Response(
                        status_code=400, success=False,
                        message=(
                            f"Tu línea de servicio disponible es ${service_available:.2f} "
                            f"y tu línea de repuestos disponible es ${parts_available:.2f}. "
                            f"Crédito insuficiente para financiar este servicio."
                        ),
                    )

            # Mark as financed and accepted
            so_model.status = "ACCEPTED"
            so_model.is_financed = 1
            so_model.down_payment_pct = dto.down_payment_pct
            await t.service_order.update(so_model)

            # Record down payment
            payment = ServiceOrderPaymentModel(
                service_order_id=order_id,
                user_id=user_id,
                amount=down_payment,
                payment_method=dto.payment_method,
                reference_number=dto.reference_number,
                status="PENDING_VERIFICATION",
                rate=dto.rate,
                rate_date=dto.rate_date,
            )
            await t.service_order_payment.add(payment)

            # Create single installment for the financed amount
            from datetime import timedelta
            installment = ServiceOrderInstallmentModel(
                service_order_id=order_id,
                amount=financed_amount,
                due_date=datetime.now(timezone.utc) + timedelta(days=30),
                status="PENDING",
            )
            t.service_order._session.add(installment)
            await t.service_order._session.flush()

            # Create commission record (5% of total order amount)
            commission_amount = round(total_price * 0.05, 2)
            commission = WorkshopCommissionModel(
                workshop_id=so_model.workshop_id,
                service_order_id=order_id,
                financed_amount=total_price,
                commission_rate=5.0,
                commission_amount=commission_amount,
                period_month=now_dt.month,
                period_year=now_dt.year,
                status="PENDING",
            )
            t.service_order._session.add(commission)
            await t.service_order._session.flush()

            # Record credit history (debt is calculated dynamically from installments)
            await t.credit_history.add_entry(
                user_id=user_id,
                type="PURCHASE",
                amount=financed_amount,
                service_line_used=financed_amount,
                description=f"Financiamiento de servicio: ${financed_amount:.2f}",
                reference_id=order_id,
            )

            late_fees_map = await self._load_late_fees_map(
                t.service_order._session, so_model.installments or []
            )
            return Response(
                status_code=200, success=True,
                message="Servicio financiado exitosamente",
                content=self._build_service_order_dto(so_model, late_fees_map),
            )

    async def pay_service_installment(
        self, installment_id: UUID, dto, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            # Find the installment
            stmt = select(ServiceOrderInstallmentModel).where(
                ServiceOrderInstallmentModel.id == installment_id
            )
            r = await t.service_order._session.execute(stmt)
            inst = r.scalars().first()
            if not inst:
                return Response(status_code=404, success=False, message="Cuota no encontrada")

            so_model = await t.service_order.get_with_relations(str(inst.service_order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")

            if inst.status == "PAID":
                return Response(status_code=400, success=False, message="Esta cuota ya fue pagada")

            # Block payment if user has any open mora
            late_fee_repo = LateFeeRepository(t.service_order._session)
            open_moras = await late_fee_repo.list_open_by_user(user_id)
            if open_moras:
                return Response(
                    status_code=400, success=False,
                    message="Tienes moras pendientes. Paga primero las moras antes de pagar cuotas.",
                )

            # Validate payment date is not before service order creation date
            if dto.paid_at:
                payment_date = dto.paid_at if isinstance(dto.paid_at, datetime) else datetime.fromisoformat(str(dto.paid_at))
                if payment_date.replace(tzinfo=timezone.utc) < so_model.created_at:
                    return Response(
                        status_code=400, success=False,
                        message="La fecha de pago no puede ser anterior a la fecha de creación de la orden.",
                    )

            inst.status = "PENDING_VERIFICATION"
            inst.payment_method = dto.payment_method
            inst.reference_number = dto.reference_number
            inst.rate = dto.rate
            inst.rate_date = dto.rate_date
            if dto.paid_at:
                inst.paid_at = dto.paid_at
            # If no rate provided, fetch BCV rate for the payment date
            if inst.rate is None and inst.paid_at:
                from src.modules.orders.infrastructure.bcv import get_bcv_rate_for_date
                rate_info = await get_bcv_rate_for_date(inst.paid_at)
                if rate_info:
                    inst.rate = rate_info.usd
                    inst.rate_date = rate_info.date
            t.service_order._session.add(inst)
            await t.service_order._session.flush()

            late_fees_map = await self._load_late_fees_map(
                t.service_order._session, so_model.installments or []
            )
            return Response(
                status_code=200, success=True,
                message="Pago de cuota registrado, pendiente de verificación",
                content=self._build_service_order_dto(so_model, late_fees_map),
            )

    async def mark_service_installment_paid(
        self, installment_id: UUID, user_id: UUID, dto: MarkServiceInstallmentPaidRequest | None = None
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            stmt = select(ServiceOrderInstallmentModel).where(
                ServiceOrderInstallmentModel.id == installment_id
            )
            r = await t.service_order._session.execute(stmt)
            inst = r.scalars().first()
            if not inst:
                return Response(status_code=404, success=False, message="Cuota no encontrada")

            so_model = await t.service_order.get_with_relations(str(inst.service_order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")

            # Check workshop owner or admin
            from src.config.models import Workshop as WorkshopModel
            ws_stmt = select(WorkshopModel).where(WorkshopModel.id == so_model.workshop_id)
            ws_r = await t.service_order._session.execute(ws_stmt)
            workshop = ws_r.scalars().first()

            is_owner = workshop and workshop.owner_id == user_id

            admin_stmt = select(UserRoleModel).where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id.in_([ROLE_NAME_TO_UUID["ADMIN"], ROLE_NAME_TO_UUID["SUPERADMIN"]]),
            )
            admin_r = await t.service_order._session.execute(admin_stmt)
            is_admin = admin_r.scalars().first() is not None

            if not is_owner and not is_admin:
                return Response(status_code=403, success=False, message="No tienes permisos para marcar cuotas como pagadas")

            if inst.status == "PAID":
                return Response(status_code=400, success=False, message="Esta cuota ya fue pagada")

            inst.status = "PAID"
            if dto and dto.paid_at:
                inst.paid_at = dto.paid_at
            elif not inst.paid_at:
                inst.paid_at = datetime.now(timezone.utc)
            t.service_order._session.add(inst)
            await t.service_order._session.flush()

            # Auto-close if all installments paid and order is DELIVERED
            all_paid = so_model.installments and all(i.status == "PAID" for i in so_model.installments)
            if all_paid and so_model.status == "DELIVERED":
                so_model.status = "CLOSED"
                await t.service_order.update(so_model)

            # Credit: add points, recalculate level (debt is dynamic)
            order_user = await t.user.get(str(so_model.user_id))
            if order_user:
                # 1. Revert mora: find open late fee for this installment → WAIVED
                late_fee_repo = LateFeeRepository(t.service_order._session)
                open_mora = await late_fee_repo.find_open_by_installment(inst.id, "SERVICE")
                if open_mora:
                    open_mora.status = "WAIVED"
                    t.service_order._session.add(open_mora)
                    await t.service_order._session.flush()
                    await t.credit_history.add_entry(
                        user_id=so_model.user_id,
                        type="LATE_FEE_WAIVED",
                        amount=open_mora.amount,
                        description=f"Mora revertida por pago de cuota: ${open_mora.amount:.2f}",
                        reference_id=open_mora.id,
                    )

                # 2. Recover penalty points: sum PENALTY entries for this installment
                penalty_entries = await late_fee_repo.find_penalty_history_by_installment(inst.id)
                recovered_points = sum(abs(e.amount) for e in penalty_entries)
                if recovered_points > 0:
                    order_user.credit_points = round(order_user.credit_points + recovered_points, 2)
                    await t.credit_history.add_entry(
                        user_id=so_model.user_id,
                        type="POINTS_RESTORED",
                        amount=recovered_points,
                        description=f"Puntos restaurados por pago de cuota atrasada: +{recovered_points:.2f}",
                        reference_id=inst.id,
                    )

                # 3. Points on time: if paid_at <= due_date, grant inst.amount points
                # For the initial installment (first one created), use so_model.created_at
                # as reference + 48h grace period, since due_date = now at creation time
                # and the workshop verifies later, making paid_at > due_date.
                from datetime import timedelta
                _paid_at = inst.paid_at
                if _paid_at and _paid_at.tzinfo is None:
                    _paid_at = _paid_at.replace(tzinfo=timezone.utc)
                _all_insts = sorted(so_model.installments or [], key=lambda x: x.created_at or datetime.min.replace(tzinfo=timezone.utc))
                _is_initial = len(_all_insts) > 0 and inst.id == _all_insts[0].id
                if _is_initial:
                    _ref_date = so_model.created_at
                    if _ref_date and _ref_date.tzinfo is None:
                        _ref_date = _ref_date.replace(tzinfo=timezone.utc)
                    is_on_time = _paid_at is None or _paid_at <= _ref_date + timedelta(hours=48)
                else:
                    _due_date = inst.due_date
                    if _due_date and _due_date.tzinfo is None:
                        _due_date = _due_date.replace(tzinfo=timezone.utc)
                    is_on_time = _paid_at is None or _paid_at <= _due_date
                if is_on_time:
                    order_user.credit_points = round(order_user.credit_points + inst.amount, 2)

                await t.user.update(order_user)
                await t.credit_history.add_entry(
                    user_id=so_model.user_id,
                    type="PAYMENT",
                    amount=inst.amount,
                    service_line_used=inst.amount,
                    description=f"Cuota de servicio pagada{' a tiempo' if is_on_time else ' tarde'}: ${inst.amount:.2f}",
                    reference_id=inst.id,
                )
                credit_svc = CreditService.__new__(CreditService)
                await credit_svc.recalculate_level(t.user._session, order_user)

            late_fees_map = await self._load_late_fees_map(
                t.service_order._session, so_model.installments or []
            )

            # Capture data for email before session closes
            _email_so_id = str(so_model.id)
            _email_so_user_id = so_model.user_id
            _email_inst_amount = inst.amount
            _email_inst_id = inst.id

            _result = Response(
                status_code=200, success=True,
                message="Cuota de servicio marcada como pagada",
                content=self._build_service_order_dto(so_model, late_fees_map),
            )

        # Send installment verified email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import installment_verified
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, ServiceOrderInstallment as _SOI
            async with _gs() as _sess:
                _u_stmt = select(_UM).where(_UM.id == _email_so_user_id)
                _u = (await _sess.execute(_u_stmt)).scalars().first()
                _inst_stmt = select(_SOI).where(_SOI.service_order_id == _email_so_id)
                _all_insts = list((await _sess.execute(_inst_stmt)).scalars().all())
                _inst_num = next((i for i, x in enumerate(_all_insts) if str(x.id) == str(_email_inst_id)), -1) + 1
                if _inst_num == 0:
                    _inst_num = 1
                _next = next((i for i in _all_insts if i.status in ("PENDING", "PENDING_VERIFICATION", "OVERDUE")), None)
                if _u:
                    _schedule = [
                        {
                            "amount": float(inst.amount),
                            "due_date": inst.due_date.strftime("%d/%m/%Y") if inst.due_date else "",
                            "status": inst.status,
                            "paid_at": inst.paid_at.strftime("%d/%m/%Y") if inst.paid_at else None,
                        }
                        for inst in _all_insts
                    ]
                    await send_email(
                        _u.email,
                        "Pago verificado - AutoTech",
                        installment_verified(
                            buyer_name=_u.first_name,
                            order_id=_email_so_id,
                            installment_number=_inst_num,
                            amount=_email_inst_amount,
                            next_due_date=_next.due_date.strftime("%d/%m/%Y") if _next else None,
                            schedule=_schedule,
                            lang=_u.language_preference or "es",
                        ),
                    )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send service installment verified email: {e}", exc_info=True)

        return _result

    async def mark_service_installment_erroneous(
        self, installment_id: UUID, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            stmt = select(ServiceOrderInstallmentModel).where(
                ServiceOrderInstallmentModel.id == installment_id
            )
            r = await t.service_order._session.execute(stmt)
            inst = r.scalars().first()
            if not inst:
                return Response(status_code=404, success=False, message="Cuota no encontrada")

            so_model = await t.service_order.get_with_relations(str(inst.service_order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")

            # Check workshop owner or admin
            from src.config.models import Workshop as WorkshopModel
            ws_stmt = select(WorkshopModel).where(WorkshopModel.id == so_model.workshop_id)
            ws_r = await t.service_order._session.execute(ws_stmt)
            workshop = ws_r.scalars().first()

            is_owner = workshop and workshop.owner_id == user_id

            admin_stmt = select(UserRoleModel).where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id.in_([ROLE_NAME_TO_UUID["ADMIN"], ROLE_NAME_TO_UUID["SUPERADMIN"]]),
            )
            admin_r = await t.service_order._session.execute(admin_stmt)
            is_admin = admin_r.scalars().first() is not None

            if not is_owner and not is_admin:
                return Response(status_code=403, success=False, message="No tienes permisos para marcar cuotas como erróneas")

            if inst.status not in ("PENDING_VERIFICATION",):
                return Response(status_code=400, success=False, message="Solo se pueden rechazar cuotas pendientes de verificación. Las cuotas verificadas no se pueden revertir.")

            # Capture original state before reverting
            original_paid_at = inst.paid_at
            original_status = inst.status

            # Revert installment to PENDING
            inst.status = "PENDING"
            inst.paid_at = None
            t.service_order._session.add(inst)
            await t.service_order._session.flush()

            # Revert any open mora (late fee) for this installment
            late_fee_repo = LateFeeRepository(t.service_order._session)
            open_mora = await late_fee_repo.find_open_by_installment(inst.id, "SERVICE")
            if open_mora:
                open_mora.status = "PENDING"
                open_mora.payment_method = "OTHER"
                open_mora.reference_number = None
                open_mora.paid_at = None
                t.service_order._session.add(open_mora)
                await t.service_order._session.flush()

            # Revert credit: remove points (debt is dynamic from installments)
            # Only revert points if the installment was actually PAID (points are awarded on mark_paid, not on registration)
            order_user = await t.user.get(str(so_model.user_id))
            if order_user and original_status == "PAID":
                # Remove points that were awarded
                _orig_paid_at = original_paid_at
                if _orig_paid_at and _orig_paid_at.tzinfo is None:
                    _orig_paid_at = _orig_paid_at.replace(tzinfo=timezone.utc)
                _due_date = inst.due_date
                if _due_date and _due_date.tzinfo is None:
                    _due_date = _due_date.replace(tzinfo=timezone.utc)
                was_on_time = _orig_paid_at is None or _orig_paid_at <= _due_date
                points_to_remove = inst.amount if was_on_time else 0
                if points_to_remove > 0:
                    order_user.credit_points = max(0.0, round(order_user.credit_points - points_to_remove, 2))

                await t.user.update(order_user)
                await t.credit_history.add_entry(
                    user_id=so_model.user_id,
                    type="PAYMENT_REVERTED",
                    amount=inst.amount,
                    service_line_used=inst.amount,
                    description=f"Cuota de servicio revertida por pago erróneo: ${inst.amount:.2f}",
                    reference_id=inst.id,
                )
                credit_svc = CreditService.__new__(CreditService)
                await credit_svc.recalculate_level(t.user._session, order_user)

            late_fees_map = await self._load_late_fees_map(
                t.service_order._session, so_model.installments or []
            )

            # Capture data for email before session closes
            _email_so_id = str(so_model.id)
            _email_so_user_id = so_model.user_id
            _email_inst_amount = inst.amount
            _email_inst_id = inst.id

            _result = Response(
                status_code=200, success=True,
                message="Cuota marcada como errónea",
                content=self._build_service_order_dto(so_model, late_fees_map),
            )

        # Send installment rejected email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import installment_rejected
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, ServiceOrderInstallment as _SOI
            async with _gs() as _sess:
                _u_stmt = select(_UM).where(_UM.id == _email_so_user_id)
                _u = (await _sess.execute(_u_stmt)).scalars().first()
                _inst_stmt = select(_SOI).where(_SOI.service_order_id == _email_so_id)
                _all_insts = list((await _sess.execute(_inst_stmt)).scalars().all())
                _inst_num = next((i for i, x in enumerate(_all_insts) if str(x.id) == str(_email_inst_id)), -1) + 1
                if _inst_num == 0:
                    _inst_num = 1
                if _u:
                    await send_email(
                        _u.email,
                        "Pago rechazado - AutoTech",
                        installment_rejected(
                            buyer_name=_u.first_name,
                            order_id=_email_so_id,
                            installment_number=_inst_num,
                            amount=_email_inst_amount,
                            lang=_u.language_preference or "es",
                        ),
                    )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send service installment rejected email: {e}", exc_info=True)

        return _result

    async def confirm_service_payment(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
            service_order_payment=ServiceOrderPaymentRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            is_owner = w_model and w_model.owner_id == user_id

            is_admin = False
            if not is_owner:
                admin_stmt = select(UserRoleModel).where(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role_id.in_([ROLE_NAME_TO_UUID["ADMIN"], ROLE_NAME_TO_UUID["SUPERADMIN"]]),
                )
                admin_r = await t.service_order._session.execute(admin_stmt)
                is_admin = admin_r.scalars().first() is not None

            if not is_owner and not is_admin:
                return Response(status_code=403, success=False, message="No tienes permisos para verificar pagos de esta orden")

            payment = (
                await t.service_order_payment._session.execute(
                    select(ServiceOrderPaymentModel)
                    .where(ServiceOrderPaymentModel.service_order_id == order_id)
                    .order_by(ServiceOrderPaymentModel.created_at.desc())
                )
            ).scalars().first()

            if not payment or payment.status != "PENDING_VERIFICATION":
                return Response(status_code=400, success=False, message="No hay pago pendiente de verificación")

            payment.status = "PAID"
            payment.paid_at = datetime.now(timezone.utc)

            if so_model.status == "REJECTED":
                total_owed = so_model.revision or 0.0
            else:
                extra = so_model.extra_charge if so_model.extra_charge_status == "APPROVED" else 0.0
                total_owed = (so_model.final_price or 0.0) + extra

            paid_sum = sum(
                p.amount for p in so_model.payments if p.status == "PAID"
            )
            so_model.is_paid = 1 if paid_sum >= total_owed else 0

            if so_model.status == "REJECTED":
                so_model.status = "CLOSED"
            elif so_model.status == "ACCEPTED":
                so_model.status = "IN_PROGRESS"

            await t.service_order.update(so_model)

            return Response(status_code=200, success=True, message="Pago confirmado", content=self._build_service_order_dto(so_model))

    async def mark_delivered(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            if so_model.status != "COMPLETED":
                return Response(status_code=400, success=False, message="El servicio debe estar completado antes de entregar")
            so_model.status = "DELIVERED"
            so_model.delivered_at = datetime.now(timezone.utc)

            # Auto-close if fully paid
            if so_model.is_financed:
                all_paid = so_model.installments and all(i.status == "PAID" for i in so_model.installments)
            else:
                all_paid = so_model.is_paid == 1
            if all_paid:
                so_model.status = "CLOSED"

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
            so_model = await t.service_order.get_with_relations(str(order_id))
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

            if dto.status == "IN_PROGRESS" and not so_model.is_paid:
                return Response(
                    status_code=400,
                    success=False,
                    message="No se puede iniciar el servicio: el pago aún no ha sido confirmado",
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
            so_model = await t.service_order.get_with_relations(str(order_id))
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

            _result = Response(
                status_code=200,
                success=True,
                message="Cargo extra agregado, pendiente de aprobación",
                content=self._build_service_order_dto(so_model),
            )

        # Send extra charge email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import service_extra_charge
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, Workshop as _WM, WorkshopService as _WSM, ServiceOrder as _SOM
            async with _gs() as _sess:
                _so = await _sess.get(_SOM, order_id)
                if _so:
                    _u = await _sess.get(_UM, _so.user_id)
                    _w = await _sess.get(_WM, _so.workshop_id)
                    _ws = await _sess.get(_WSM, _so.workshop_service_id) if _so.workshop_service_id else None
                    _svc_name = _ws.name if _ws else "Servicio"
                    _ws_name = _w.name if _w else "AutoTech"
                    if _u:
                        await send_email(
                            _u.email,
                            "Cargo extra pendiente - AutoTech",
                            service_extra_charge(
                                buyer_name=_u.first_name,
                                service_name=_svc_name,
                                workshop_name=_ws_name,
                                extra_charge=dto.extra_charge,
                                note=dto.extra_charge_note,
                                order_id=str(order_id),
                                lang=_u.language_preference or "es",
                            ),
                        )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send service extra charge email: {e}", exc_info=True)

        return _result

    async def mark_service_shipped(self, order_id: UUID, user_id: UUID, dto: MarkServiceShippedRequest) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
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
            _result = Response(status_code=200, success=True, message="Orden marcada como enviada", content=self._build_service_order_dto(so_model))

        # Send service shipped email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import service_shipped
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, Workshop as _WM, WorkshopService as _WSM, ServiceOrder as _SOM
            async with _gs() as _sess:
                _so = await _sess.get(_SOM, order_id)
                if _so:
                    _u = await _sess.get(_UM, _so.user_id)
                    _w = await _sess.get(_WM, _so.workshop_id)
                    _ws = await _sess.get(_WSM, _so.workshop_service_id) if _so.workshop_service_id else None
                    _svc_name = _ws.name if _ws else "Servicio"
                    _ws_name = _w.name if _w else "AutoTech"
                    if _u:
                        await send_email(
                            _u.email,
                            "Vehículo enviado - AutoTech",
                            service_shipped(
                                buyer_name=_u.first_name,
                                service_name=_svc_name,
                                workshop_name=_ws_name,
                                tracking_number=dto.tracking_number,
                                shipping_notes=dto.shipping_notes,
                                order_id=str(order_id),
                                lang=_u.language_preference or "es",
                            ),
                        )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send service shipped email: {e}", exc_info=True)

        return _result

    async def mark_service_received(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No eres el comprador de esta orden")
            if so_model.status not in ("SHIPPED", "COMPLETED"):
                return Response(status_code=400, success=False, message="La orden no está lista para ser recibida")
            so_model.status = "DELIVERED"
            so_model.delivered_at = datetime.now(timezone.utc)

            # Auto-close if fully paid
            if so_model.is_financed:
                all_paid = so_model.installments and all(i.status == "PAID" for i in so_model.installments)
            else:
                all_paid = so_model.is_paid == 1
            if all_paid:
                so_model.status = "CLOSED"

            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Recepción confirmada", content=self._build_service_order_dto(so_model))

    async def cancel_service_order(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(service_order=ServiceOrderRepository) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta orden")
            if so_model.status not in ("PENDING", "DROPPED_OFF"):
                return Response(status_code=400, success=False, message="Solo se pueden cancelar órdenes pendientes")
            so_model.status = "CANCELLED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Orden cancelada exitosamente", content=self._build_service_order_dto(so_model))

    async def close_service_as_client(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            if so_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No eres el comprador de esta orden")
            if so_model.status != "DELIVERED":
                return Response(status_code=400, success=False, message="La orden debe estar entregada para cerrar")
            so_model.closed_by_client = 1
            # Only close if all installments are paid
            if so_model.is_financed:
                all_paid = so_model.installments and all(i.status == "PAID" for i in so_model.installments)
            else:
                all_paid = so_model.is_paid == 1
            if all_paid and so_model.closed_by_workshop:
                so_model.status = "CLOSED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Orden cerrada", content=self._build_service_order_dto(so_model))

    async def close_service_as_workshop(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
            if not so_model:
                return Response(status_code=404, success=False, message="Orden de servicio no encontrada")
            w_model = await t.workshop.get(str(so_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(status_code=403, success=False, message="No eres el dueño del taller")
            if so_model.status != "DELIVERED":
                return Response(status_code=400, success=False, message="La orden debe estar entregada para cerrar")
            # Only close if all installments are paid
            if so_model.is_financed:
                all_paid = so_model.installments and all(i.status == "PAID" for i in so_model.installments)
            else:
                all_paid = so_model.is_paid == 1
            if not all_paid:
                return Response(status_code=400, success=False, message="Todas las cuotas deben estar pagadas para cerrar la orden")
            so_model.closed_by_workshop = 1
            so_model.closed_by_client = 1
            so_model.status = "CLOSED"
            await t.service_order.update(so_model)
            return Response(status_code=200, success=True, message="Orden cerrada por el taller", content=self._build_service_order_dto(so_model))

    async def rate_service_order_workshop(self, order_id: UUID, user_id: UUID, dto: RateServiceOrderRequest) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
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
            user=UserRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
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

            u_model = await t.user.get(str(so_model.user_id))
            if u_model:
                # Service order workshop ratings for this client
                all_so_ratings = select(ServiceOrderModel.workshop_rating).where(
                    ServiceOrderModel.user_id == so_model.user_id,
                    ServiceOrderModel.workshop_rating.isnot(None),
                )
                r = await t.user._session.execute(all_so_ratings)
                so_ratings = [row[0] for row in r if row[0] is not None]
                # Purchase order reviews targeting this client
                or_stmt = select(OrderReviewModel.rating).where(
                    OrderReviewModel.target_role == "CLIENT",
                    OrderReviewModel.order_id.in_(
                        select(OrderModel.id).where(OrderModel.user_id == so_model.user_id)
                    ),
                )
                or_r = await t.user._session.execute(or_stmt)
                or_ratings = [row[0] for row in or_r if row[0] is not None]
                all_ratings = so_ratings + or_ratings
                if all_ratings:
                    u_model.client_average_rating = round(sum(all_ratings) / len(all_ratings), 1)
                    u_model.client_rating_count = len(all_ratings)
                    await t.user.update(u_model)

            return Response(status_code=200, success=True, message="Cliente calificado exitosamente", content=self._build_service_order_dto(so_model))

    async def approve_extra_charge(
        self, order_id: UUID, user_id: UUID
    ) -> Response:
        async with self._transaction(
            service_order=ServiceOrderRepository,
        ) as t:
            so_model = await t.service_order.get_with_relations(str(order_id))
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
            so_model = await t.service_order.get_with_relations(str(order_id))
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

    async def _load_late_fees_map(
        self, session, installments
    ) -> dict:
        """Build a map of installment_id -> {status, amount} for open late fees."""
        if not installments:
            return {}
        from src.config.models import LateFee as LateFeeModel
        inst_ids = [inst.id for inst in installments]
        stmt = select(LateFeeModel).where(
            LateFeeModel.installment_id.in_(inst_ids),
            LateFeeModel.installment_type == "SERVICE",
            LateFeeModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
        )
        r = await session.execute(stmt)
        fees = r.scalars().all()
        return {
            str(fee.installment_id): {"status": fee.status, "amount": fee.amount}
            for fee in fees
        }

    def _build_service_order_dto(
        self, o: ServiceOrderModel, late_fees_map: dict | None = None
    ) -> ServiceOrderDTO:
        final_price = o.final_price if o.final_price is not None else o.base_price
        latest_payment = None
        if o.payments:
            latest_payment = sorted(
                o.payments, key=lambda p: p.created_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True
            )[0]
        return ServiceOrderDTO(
            id=o.id,
            user_id=o.user_id,
            workshop_id=o.workshop_id,
            service_id=o.service_id,
            vehicle_id=o.vehicle_id,
            service_name=o.workshop_service.service_name if o.workshop_service else "",
            workshop_name=o.workshop.name if o.workshop else None,
            workshop_rif=o.workshop.rif if o.workshop else None,
            workshop_address=o.workshop.address if o.workshop else None,
            vehicle_brand=o.vehicle.brand if o.vehicle else "",
            vehicle_model=o.vehicle.model if o.vehicle else "",
            vehicle_license_plate=o.vehicle.license_plate if o.vehicle else "",
            user_first_name=o.user.first_name if o.user else "",
            user_last_name=o.user.last_name if o.user else "",
            user_ci=o.user.ci if o.user else "",
            user_email=o.user.email if o.user else "",
            user_client_rating=o.user.client_average_rating if o.user else None,
            user_client_rating_count=o.user.client_rating_count if o.user else None,
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
            revision=o.revision,
            is_paid=bool(o.is_paid),
            is_financed=bool(o.is_financed),
            down_payment_pct=o.down_payment_pct,
            payment_status=latest_payment.status if latest_payment else None,
            created_at=o.created_at,
            completed_at=o.completed_at,
            delivered_at=o.delivered_at,
            ratings=ServiceOrderRatingInfo(
                client_rating=o.client_rating,
                client_rated=o.client_rating is not None,
                client_review=o.client_review,
                workshop_rating=o.workshop_rating,
                workshop_rated=o.workshop_rating is not None,
                workshop_review=o.workshop_review,
            ),
            payments=[
                ServiceOrderPaymentDTO(
                    id=p.id,
                    amount=p.amount,
                    payment_method=p.payment_method,
                    reference_number=p.reference_number,
                    status=p.status,
                    paid_at=p.paid_at,
                    rate=p.rate,
                    rate_date=p.rate_date,
                    created_at=p.created_at,
                )
                for p in (o.payments or [])
            ],
            installments=[
                ServiceOrderInstallmentDTO(
                    id=inst.id,
                    amount=inst.amount,
                    due_date=inst.due_date,
                    payment_method=inst.payment_method,
                    reference_number=inst.reference_number,
                    status=inst.status,
                    paid_at=inst.paid_at,
                    rate=inst.rate,
                    rate_date=inst.rate_date,
                    created_at=inst.created_at,
                    late_fee_status=(
                        late_fees_map.get(str(inst.id), {}).get("status")
                        if late_fees_map
                        else None
                    ),
                    late_fee_amount=(
                        late_fees_map.get(str(inst.id), {}).get("amount")
                        if late_fees_map
                        else None
                    ),
                )
                for inst in (o.installments or [])
            ],
        )


def get_service_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> ServiceService:
    return ServiceService(transaction)
