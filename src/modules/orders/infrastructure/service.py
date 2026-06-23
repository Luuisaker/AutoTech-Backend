from typing import Type
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import Depends

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.orders.infrastructure.mapper import (
    OrderMapper,
    OrderItemMapper,
)
from src.modules.orders.application.create import (
    CheckoutRequest,
    PayInstallmentRequest,
    OrderDTO,
    OrderItemDTO,
    OrderListDTO,
    InstallmentDTO,
    InstallmentListDTO,
)
from src.modules.orders.domain.entity import Order, OrderItem
from src.modules.orders.infrastructure.repository import (
    OrderRepository,
    OrderItemRepository,
    InstallmentRepository,
    TransactionRepository,
)
from src.modules.cart.infrastructure.repository import (
    CartRepository,
    CartItemRepository,
)
from src.modules.parts.infrastructure.repository import PartRepository
from src.modules.vehicles.infrastructure.repository import VehicleRepository
from src.modules.workshops.infrastructure.repository import WorkshopRepository
from src.config.models import Installment as InstallmentModel
from src.config.models import Transaction as TransactionModel
from src.config.models import VehicleHistoryLog as VehicleHistoryLogModel
from src.modules.parts.infrastructure.repository import (
    VehicleHistoryLogRepository,
)


class OrderService:
    __order_mapper = OrderMapper()
    __item_mapper = OrderItemMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    async def checkout(self, dto: CheckoutRequest, user_id: UUID) -> Response:
        async with self._transaction(
            cart=CartRepository,
            cart_item=CartItemRepository,
            order=OrderRepository,
            order_item=OrderItemRepository,
            installment=InstallmentRepository,
            part=PartRepository,
            workshop=WorkshopRepository,
            vehicle=VehicleRepository,
            vehicle_history_log=VehicleHistoryLogRepository,
        ) as t:
            # Validate vehicle
            v_model = await t.vehicle.get(str(dto.vehicle_id))
            if not v_model or v_model.owner_id != user_id:
                return Response(
                    status_code=400,
                    success=False,
                    message="Vehículo inválido o no te pertenece",
                )

            # Get cart
            cart = await t.cart.get_by_user(str(user_id))
            if not cart or not cart.items:
                return Response(
                    status_code=400,
                    success=False,
                    message="Carrito vacío",
                )

            # Validate stock for all items
            cart_items_data = []
            for ci in cart.items:
                p_model = await t.part.get(str(ci.part_id))
                if not p_model or not p_model.is_active:
                    return Response(
                        status_code=400,
                        success=False,
                        message=f"Producto no disponible: {ci.part_id}",
                    )
                if p_model.stock < ci.quantity:
                    return Response(
                        status_code=400,
                        success=False,
                        message=f"Stock insuficiente para {p_model.name}",
                    )
                w_model = await t.workshop.get(str(p_model.workshop_id))
                if not w_model or not w_model.is_certified:
                    return Response(
                        status_code=400,
                        success=False,
                        message=f"El taller de {p_model.name} no está certificado",
                    )
                if p_model.workshop_id == user_id:
                    return Response(
                        status_code=400,
                        success=False,
                        message="No puedes comprar tus propios productos",
                    )
                cart_items_data.append((ci, p_model))

            # Calculate totals
            total = sum(p.price * ci.quantity for ci, p in cart_items_data)
            total = round(total, 2)

            down_payment = 0.0
            financed_amount = 0.0
            installment_count = dto.installment_count

            if installment_count > 0:
                # Check all items allow installments
                for ci, p in cart_items_data:
                    if not p.allows_installments:
                        return Response(
                            status_code=400,
                            success=False,
                            message=f"{p.name} no permite financiamiento",
                        )
                min_pct = max(p.installment_min_percentage for _, p in cart_items_data)
                down_payment = round(total * (min_pct / 100.0), 2)
                financed_amount = round(total - down_payment, 2)
                status = "FINANCED"
            else:
                status = "PAID"

            # Create Order
            order_entity = Order(
                user_id=user_id,
                vehicle_id=dto.vehicle_id,
                mileage=dto.mileage,
                total_amount=total,
                status=status,
            )
            order_model = await t.order.add(self.__order_mapper.to_model(order_entity))

            # Create OrderItems & decrease stock
            for ci, p in cart_items_data:
                item_entity = OrderItem(
                    order_id=order_model.id,
                    part_id=ci.part_id,
                    quantity=ci.quantity,
                    unit_price=p.price,
                )
                await t.order_item.add(self.__item_mapper.to_model(item_entity))
                p.stock -= ci.quantity
                await t.part.update(p)

            # Create payments
            if down_payment > 0:
                inst_model = InstallmentModel(
                    order_id=order_model.id,
                    amount=down_payment,
                    due_date=datetime.now(timezone.utc),
                    status="PAID",
                    paid_at=datetime.now(timezone.utc),
                )
                await t.installment.add(inst_model)

                installment_amount = round(financed_amount / installment_count, 2)
                for i in range(installment_count):
                    due = datetime.now(timezone.utc) + timedelta(days=30 * (i + 1))
                    inst_model = InstallmentModel(
                        order_id=order_model.id,
                        amount=installment_amount,
                        due_date=due,
                        status="PENDING",
                    )
                    await t.installment.add(inst_model)
            else:
                inst_model = InstallmentModel(
                    order_id=order_model.id,
                    amount=total,
                    due_date=datetime.now(timezone.utc),
                    status="PAID",
                    paid_at=datetime.now(timezone.utc),
                )
                await t.installment.add(inst_model)

                # VehicleHistoryLog for full payment
                for ci, p in cart_items_data:
                    log = VehicleHistoryLogModel(
                        vehicle_id=dto.vehicle_id,
                        workshop_id=p.workshop_id,
                        log_date=datetime.now(timezone.utc),
                        mileage=dto.mileage,
                        description=f"Compra de {p.name} x{ci.quantity}",
                    )
                    await t.vehicle_history_log.add(log)

            # Clear cart
            for ci in cart.items:
                await t.cart._session.delete(ci)
            await t.cart._session.delete(cart)

        return Response(
            status_code=201,
            success=True,
            message="Compra realizada exitosamente",
            content=OrderDTO(
                id=order_model.id,
                vehicle_id=dto.vehicle_id,
                total_amount=total,
                down_payment=down_payment,
                financed_amount=financed_amount,
                installment_count=installment_count,
                status=status,
                items=[
                    OrderItemDTO(
                        id=item_model.id,
                        part_id=item_model.part_id,
                        part_name=item_model.part.name
                        if hasattr(item_model, "part")
                        else "",
                        quantity=item_model.quantity,
                        unit_price=item_model.unit_price,
                    )
                    for item_model in (
                        await t.order_item.list_by_order(str(order_model.id))
                    )
                ],
                created_at=order_model.created_at,
            ),
        )

    async def list_mine(self, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
        ) as t:
            orders = await t.order.list_by_user(str(user_id))

        return Response(
            status_code=200,
            success=True,
            content=OrderListDTO(
                orders=[
                    OrderDTO(
                        id=o.id,
                        vehicle_id=o.vehicle_id,
                        total_amount=o.total_amount,
                        down_payment=0.0,
                        financed_amount=0.0,
                        installment_count=0,
                        status=o.status,
                        items=[
                            OrderItemDTO(
                                id=i.id,
                                part_id=i.part_id,
                                part_name=i.part.name
                                if hasattr(i, "part") and i.part
                                else "",
                                quantity=i.quantity,
                                unit_price=i.unit_price,
                            )
                            for i in o.items
                        ],
                        created_at=o.created_at,
                    )
                    for o in orders
                ]
            ),
        )

    async def get_installments(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
            installment=InstallmentRepository,
        ) as t:
            order_model = await t.order.get(str(order_id))
            if not order_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden no encontrada",
                )
            if order_model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a esta orden",
                )

            installments = await t.installment.list_by_order(str(order_id))

        return Response(
            status_code=200,
            success=True,
            content=InstallmentListDTO(
                installments=[
                    InstallmentDTO(
                        id=inst.id,
                        amount=inst.amount,
                        due_date=inst.due_date,
                        status=inst.status,
                        paid_at=inst.paid_at,
                    )
                    for inst in installments
                ]
            ),
        )

    async def pay_installment(
        self,
        installment_id: UUID,
        user_id: UUID,
        dto: PayInstallmentRequest,
    ) -> Response:
        async with self._transaction(
            order=OrderRepository,
            installment=InstallmentRepository,
            transaction=TransactionRepository,
            vehicle_history_log=VehicleHistoryLogRepository,
        ) as t:
            inst_model = await t.installment.get(str(installment_id))
            if not inst_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Cuota no encontrada",
                )

            order_model = await t.order.get(str(inst_model.order_id))
            if not order_model or order_model.user_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes acceso a esta cuota",
                )

            if inst_model.status == "PAID":
                return Response(
                    status_code=400,
                    success=False,
                    message="Esta cuota ya fue pagada",
                )

            inst_model.status = "PAID"
            inst_model.paid_at = datetime.now(timezone.utc)
            await t.installment.update(inst_model)

            txn_model = TransactionModel(
                order_id=order_model.id,
                installment_id=inst_model.id,
                payer_user_id=user_id,
                amount=inst_model.amount,
                payment_method=dto.payment_method,
                status="COMPLETED",
            )
            await t.transaction.add(txn_model)

            # Check if all installments paid
            all_inst = await t.installment.list_by_order(str(order_model.id))
            if all(i.status == "PAID" for i in all_inst):
                order_model.status = "PAID"
                await t.order.update(order_model)

                # VehicleHistoryLog for each order item
                from src.config.models import OrderItem as OrderItemModel
                from sqlalchemy import select as sa_select

                stmt = sa_select(OrderItemModel).where(
                    OrderItemModel.order_id == order_model.id
                )
                r = await t.order._session.execute(stmt)
                items = r.scalars().all()

                for item in items:
                    from src.config.models import Part as PartModel

                    p_stmt = sa_select(PartModel).where(PartModel.id == item.part_id)
                    pr = await t.order._session.execute(p_stmt)
                    p_model = pr.scalar_one_or_none()
                    log = VehicleHistoryLogModel(
                        vehicle_id=order_model.vehicle_id,
                        workshop_id=p_model.workshop_id if p_model else None,
                        log_date=datetime.now(timezone.utc),
                        mileage=order_model.mileage,
                        description="Compra de repuesto completada",
                    )
                    await t.vehicle_history_log.add(log)

        return Response(
            status_code=200,
            success=True,
            message="Cuota pagada exitosamente",
            content=InstallmentDTO(
                id=inst_model.id,
                amount=inst_model.amount,
                due_date=inst_model.due_date,
                status=inst_model.status,
                paid_at=inst_model.paid_at,
            ),
        )


def get_order_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> OrderService:
    return OrderService(transaction)
