from typing import Type
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.parts.infrastructure.mapper import PartMapper, PartPurchaseMapper
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
from src.modules.parts.domain.entity import Part, PartPurchase
from src.modules.parts.domain.types import PartCategory, PartCondition
from src.modules.parts.infrastructure.repository import (
    PartRepository,
    PartPurchaseRepository,
    PartPaymentRepository,
    VehicleHistoryLogRepository,
)
from src.modules.workshops.infrastructure.repository import (
    WorkshopRepository,
)
from src.modules.vehicles.infrastructure.repository import (
    VehicleRepository,
)
from src.config.models import PartPayment as PartPaymentModel
from src.config.models import VehicleHistoryLog as VehicleHistoryLogModel


class PartService:
    __mapper = PartMapper()
    __purchase_mapper = PartPurchaseMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    @staticmethod
    def get_categories() -> Response:
        return Response(
            status_code=200,
            success=True,
            content=PartCategoryListDTO(categories=[c.value for c in PartCategory]),
        )

    @staticmethod
    def get_conditions() -> Response:
        return Response(
            status_code=200,
            success=True,
            content=PartCategoryListDTO(categories=[c.value for c in PartCondition]),
        )

    async def create(self, dto: CreatePartRequest, user_id: UUID) -> Response:
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
                    message="El taller debe estar certificado para publicar productos",
                )

        part_entity = Part(
            workshop_id=dto.workshop_id,
            name=dto.name,
            description=dto.description,
            price=dto.price,
            stock=dto.stock,
            condition=dto.condition,
            category=dto.category,
            allows_installments=dto.allows_installments,
            installment_min_percentage=dto.installment_min_percentage,
        )

        async with self._transaction(part=PartRepository) as t:
            p_model = await t.part.add(self.__mapper.to_model(part_entity))

        return Response(
            status_code=201,
            success=True,
            message="Producto publicado exitosamente",
            content=PartDTO.model_validate(self.__mapper.to_entity(p_model)),
        )

    async def list(
        self,
        query: str | None = None,
        category: str | None = None,
        condition: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        certified_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Response:
        async with self._transaction(part=PartRepository) as t:
            parts = await t.part.search(
                query=query,
                category=category,
                condition=condition,
                min_price=min_price,
                max_price=max_price,
                certified_only=certified_only,
                offset=offset,
                limit=limit,
            )

        return Response(
            status_code=200,
            success=True,
            content=PartListDTO(
                parts=[
                    PartDTO.model_validate(self.__mapper.to_entity(p)) for p in parts
                ]
            ),
        )

    async def list_by_workshop(
        self, workshop_id: UUID, offset: int = 0, limit: int = 100
    ) -> Response:
        async with self._transaction(part=PartRepository) as t:
            parts = await t.part.list_by_workshop(str(workshop_id), offset, limit)

        return Response(
            status_code=200,
            success=True,
            content=PartListDTO(
                parts=[
                    PartDTO.model_validate(self.__mapper.to_entity(p)) for p in parts
                ]
            ),
        )

    async def get_by_id(self, part_id: UUID) -> Response:
        async with self._transaction(part=PartRepository) as t:
            p_model = await t.part.get(str(part_id))

        if not p_model:
            return Response(
                status_code=404,
                success=False,
                message="Producto no encontrado",
            )

        return Response(
            status_code=200,
            success=True,
            content=PartDTO.model_validate(self.__mapper.to_entity(p_model)),
        )

    async def update(
        self, part_id: UUID, dto: UpdatePartRequest, user_id: UUID
    ) -> Response:
        async with self._transaction(
            part=PartRepository, workshop=WorkshopRepository
        ) as t:
            p_model = await t.part.get(str(part_id))

            if not p_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Producto no encontrado",
                )

            w_model = await t.workshop.get(str(p_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            if dto.name is not None:
                p_model.name = dto.name
            if dto.description is not None:
                p_model.description = dto.description
            if dto.price is not None:
                p_model.price = dto.price
            if dto.stock is not None:
                p_model.stock = dto.stock
            if dto.condition is not None:
                p_model.condition = dto.condition
            if dto.category is not None:
                p_model.category = dto.category
            if dto.allows_installments is not None:
                p_model.allows_installments = dto.allows_installments
            if dto.installment_min_percentage is not None:
                p_model.installment_min_percentage = dto.installment_min_percentage
            if dto.is_active is not None:
                p_model.is_active = dto.is_active

            p_model = await t.part.update(p_model)

        return Response(
            status_code=200,
            success=True,
            message="Producto actualizado exitosamente",
            content=PartDTO.model_validate(self.__mapper.to_entity(p_model)),
        )

    async def deactivate(self, part_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            part=PartRepository, workshop=WorkshopRepository
        ) as t:
            p_model = await t.part.get(str(part_id))

            if not p_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Producto no encontrado",
                )

            w_model = await t.workshop.get(str(p_model.workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            p_model.is_active = 0
            await t.part.update(p_model)

        return Response(
            status_code=200,
            success=True,
            message="Producto desactivado exitosamente",
        )

    async def purchase(self, dto: PurchasePartRequest, user_id: UUID) -> Response:
        async with self._transaction(
            part=PartRepository,
            workshop=WorkshopRepository,
            vehicle=VehicleRepository,
            purchase=PartPurchaseRepository,
            payment=PartPaymentRepository,
            vehicle_history_log=VehicleHistoryLogRepository,
        ) as t:
            p_model = await t.part.get(str(dto.part_id))

            if not p_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Producto no encontrado",
                )

            if not p_model.is_active:
                return Response(
                    status_code=400,
                    success=False,
                    message="Este producto no está disponible",
                )

            if p_model.stock < dto.quantity:
                return Response(
                    status_code=400,
                    success=False,
                    message="Stock insuficiente",
                )

            v_model = await t.vehicle.get(str(dto.vehicle_id))
            if not v_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Vehículo no encontrado",
                )
            if v_model.owner_id != user_id:
                return Response(
                    status_code=400,
                    success=False,
                    message="El vehículo no te pertenece",
                )

            w_model = await t.workshop.get(str(p_model.workshop_id))
            if not w_model or not w_model.is_certified:
                return Response(
                    status_code=400,
                    success=False,
                    message="El taller del producto no está certificado",
                )

            if p_model.workshop_id == user_id:
                return Response(
                    status_code=400,
                    success=False,
                    message="No puedes comprar tu propio producto",
                )

            total = p_model.price * dto.quantity
            down_payment = 0.0
            financed_amount = 0.0
            installment_count = 0
            status = "PAID"

            if p_model.allows_installments and dto.installment_count > 0:
                down_payment = total * (p_model.installment_min_percentage / 100.0)
                financed_amount = total - down_payment
                installment_count = dto.installment_count
                status = "FINANCED"

            purchase_entity = PartPurchase(
                part_id=dto.part_id,
                user_id=user_id,
                workshop_id=p_model.workshop_id,
                vehicle_id=dto.vehicle_id,
                mileage=dto.mileage,
                quantity=dto.quantity,
                unit_price=p_model.price,
                total_amount=total,
                down_payment=down_payment,
                financed_amount=financed_amount,
                installment_count=installment_count,
                status=status,
            )

            purchase_model = await t.purchase.add(
                self.__purchase_mapper.to_model(purchase_entity)
            )

            # Create down payment record
            if down_payment > 0:
                payment_model = PartPaymentModel(
                    purchase_id=purchase_model.id,
                    amount=down_payment,
                    due_date=datetime.now(timezone.utc),
                    status="PAID",
                    paid_at=datetime.now(timezone.utc),
                )
                await t.payment.add(payment_model)

                # Create remaining installments
                installment_amount = round(financed_amount / installment_count, 2)
                for i in range(installment_count):
                    due_date = datetime.now(timezone.utc) + timedelta(days=30 * (i + 1))
                    payment_model = PartPaymentModel(
                        purchase_id=purchase_model.id,
                        amount=installment_amount,
                        due_date=due_date,
                        status="PENDING",
                    )
                    await t.payment.add(payment_model)
            else:
                # Single full payment
                payment_model = PartPaymentModel(
                    purchase_id=purchase_model.id,
                    amount=total,
                    due_date=datetime.now(timezone.utc),
                    status="PAID",
                    paid_at=datetime.now(timezone.utc),
                )
                await t.payment.add(payment_model)

            # Decrease stock
            p_model.stock -= dto.quantity
            await t.part.update(p_model)

            # Create VehicleHistoryLog for immediate full payment
            if status == "PAID":
                log_entry = VehicleHistoryLogModel(
                    vehicle_id=dto.vehicle_id,
                    workshop_id=p_model.workshop_id,
                    log_date=datetime.now(timezone.utc),
                    mileage=dto.mileage,
                    description=f"Compra de {p_model.name} x{dto.quantity}",
                )
                await t.vehicle_history_log.add(log_entry)

        return Response(
            status_code=201,
            success=True,
            message="Compra realizada exitosamente",
            content=PartPurchaseDTO.model_validate(
                self.__purchase_mapper.to_entity(purchase_model)
            ),
        )

    async def list_purchases_by_user(
        self, user_id: UUID, offset: int = 0, limit: int = 100
    ) -> Response:
        async with self._transaction(purchase=PartPurchaseRepository) as t:
            purchases = await t.purchase.list_by_user(str(user_id), offset, limit)

        return Response(
            status_code=200,
            success=True,
            content=PartPurchaseListDTO(
                purchases=[
                    PartPurchaseDTO.model_validate(self.__purchase_mapper.to_entity(p))
                    for p in purchases
                ]
            ),
        )

    async def list_purchases_by_workshop(
        self, workshop_id: UUID, offset: int = 0, limit: int = 100
    ) -> Response:
        async with self._transaction(purchase=PartPurchaseRepository) as t:
            purchases = await t.purchase.list_by_workshop(
                str(workshop_id), offset, limit
            )

        return Response(
            status_code=200,
            success=True,
            content=PartPurchaseListDTO(
                purchases=[
                    PartPurchaseDTO.model_validate(self.__purchase_mapper.to_entity(p))
                    for p in purchases
                ]
            ),
        )

    async def get_purchase_payments(self, purchase_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            purchase=PartPurchaseRepository, payment=PartPaymentRepository
        ) as t:
            purchase_model = await t.purchase.get(str(purchase_id))

            if not purchase_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Compra no encontrada",
                )

            if purchase_model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a esta compra",
                )

            payments = await t.payment.list_by_purchase(str(purchase_id))

        return Response(
            status_code=200,
            success=True,
            content=PartPaymentListDTO(
                payments=[PartPaymentDTO.model_validate(p) for p in payments]
            ),
        )

    async def record_payment(
        self, payment_id: UUID, user_id: UUID, dto: RecordPaymentRequest
    ) -> Response:
        async with self._transaction(
            payment=PartPaymentRepository,
            purchase=PartPurchaseRepository,
            vehicle_history_log=VehicleHistoryLogRepository,
        ) as t:
            payment_model = await t.payment.get(str(payment_id))

            if not payment_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Pago no encontrado",
                )

            purchase_model = await t.purchase.get(str(payment_model.purchase_id))

            if not purchase_model or purchase_model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a este pago",
                )

            if payment_model.status == "PAID":
                return Response(
                    status_code=400,
                    success=False,
                    message="Este pago ya fue realizado",
                )

            payment_model.payment_method = dto.payment_method
            payment_model.reference_number = dto.reference_number
            payment_model.status = "PAID"
            payment_model.paid_at = datetime.now(timezone.utc)

            payment_model = await t.payment.update(payment_model)

            # Check if all payments are PAID -> mark purchase as PAID
            all_payments = await t.payment.list_by_purchase(
                str(payment_model.purchase_id)
            )
            if all(p.status == "PAID" for p in all_payments):
                purchase_model.status = "PAID"
                await t.purchase.update(purchase_model)

                # Create VehicleHistoryLog entry
                log_entry = VehicleHistoryLogModel(
                    vehicle_id=purchase_model.vehicle_id,
                    workshop_id=purchase_model.workshop_id,
                    log_date=datetime.now(timezone.utc),
                    mileage=purchase_model.mileage,
                    description="Compra de repuesto completada",
                )
                await t.vehicle_history_log.add(log_entry)

        return Response(
            status_code=200,
            success=True,
            message="Pago registrado exitosamente",
            content=PartPaymentDTO.model_validate(payment_model),
        )

    async def list_workshop_sales(
        self, workshop_id: UUID, user_id: UUID, offset: int = 0, limit: int = 100
    ) -> Response:
        async with self._transaction(
            workshop=WorkshopRepository, purchase=PartPurchaseRepository
        ) as t:
            w_model = await t.workshop.get(str(workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            purchases = await t.purchase.list_by_workshop(
                str(workshop_id), offset, limit
            )

        return Response(
            status_code=200,
            success=True,
            content=PartPurchaseListDTO(
                purchases=[
                    PartPurchaseDTO.model_validate(self.__purchase_mapper.to_entity(p))
                    for p in purchases
                ]
            ),
        )


def get_part_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> PartService:
    return PartService(transaction)
