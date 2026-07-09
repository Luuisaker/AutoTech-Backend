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
    WorkshopCheckoutInput,
    CheckoutItemInput,
    PayInstallmentRequest,
    MarkInstallmentPaidRequest,
    ConfirmPaymentRequest,
    MarkShippedRequest,
    OrderDTO,
    OrderItemDTO,
    OrderListDTO,
    InstallmentDTO,
    InstallmentListDTO,
    WorkshopOrderDTO,
    WorkshopOrderListDTO,
    RateOrderRequest,
    OrderRatingInfo,
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
from src.config.models import (
    Installment as InstallmentModel,
    Transaction as TransactionModel,
    VehicleHistoryLog as VehicleHistoryLogModel,
    Order as OrderModel,
    OrderItem as OrderItemModel,
    Part as PartModel,
    UserRole as UserRoleModel,
    OrderReview as OrderReviewModel,
)
from src.modules.parts.infrastructure.repository import (
    VehicleHistoryLogRepository,
)
from sqlalchemy import select


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
            # Get vehicle (first available if not specified)
            vehicle_id = dto.vehicle_id
            if not vehicle_id:
                vehicles = await t.vehicle.list_by_owner(str(user_id))
                if not vehicles:
                    return Response(
                        status_code=400,
                        success=False,
                        message="Debes tener al menos un vehículo registrado",
                    )
                vehicle_id = vehicles[0].id
            else:
                v_model = await t.vehicle.get(str(vehicle_id))
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

            # Build per-workshop item configs from dto.workshops
            workshop_configs: dict[str, WorkshopCheckoutInput] = {}
            item_configs: dict[str, tuple[str, CheckoutItemInput]] = {}
            for wc in dto.workshops:
                wid = str(wc.workshop_id)
                workshop_configs[wid] = wc
                for cfg in wc.items:
                    item_configs[cfg.cart_item_id] = (wid, cfg)

            # Validate stock and collect items with part + workshop info
            cart_items_data: list[tuple] = []
            for ci in cart.items:
                entry = item_configs.get(str(ci.id))
                if not entry:
                    continue
                wid, cfg = entry
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
                if str(p_model.workshop_id) == str(user_id):
                    return Response(
                        status_code=400,
                        success=False,
                        message="No puedes comprar tus propios productos",
                    )
                cart_items_data.append((ci, p_model, w_model, cfg, wid))

            # Group by workshop
            workshop_groups: dict[str, list] = {}
            for ci, p, w, cfg, wid in cart_items_data:
                if wid not in workshop_groups:
                    workshop_groups[wid] = []
                workshop_groups[wid].append((ci, p, w, cfg))

            # Validate all workshops have configs
            for wid in workshop_groups:
                if wid not in workshop_configs:
                    return Response(
                        status_code=400,
                        success=False,
                        message=f"Configuración de envío faltante para taller {wid}",
                    )

            created_orders: list[OrderModel] = []

            for wid, group in workshop_groups.items():
                wc = workshop_configs[wid]

                # Calculate workshop total
                group_total = round(
                    sum(p.price * ci.quantity for ci, p, _, _ in group), 2
                )

                # Check installments for this workshop group
                group_down_payment = 0.0
                group_financed_amount = 0.0
                group_any_installments = any(
                    cfg.down_payment_percentage is not None
                    and cfg.down_payment_percentage < 100
                    for _, _, _, cfg in group
                )

                if group_any_installments:
                    for ci, p, _, cfg in group:
                        if (
                            cfg.down_payment_percentage is not None
                            and cfg.down_payment_percentage < 100
                        ):
                            if not p.allows_installments:
                                return Response(
                                    status_code=400,
                                    success=False,
                                    message=f"{p.name} no permite financiamiento",
                                )
                            if (
                                cfg.down_payment_percentage
                                < p.installment_min_percentage
                            ):
                                return Response(
                                    status_code=400,
                                    success=False,
                                    message=f"El porcentaje inicial mínimo para {p.name} es {p.installment_min_percentage}%",
                                )

                    item_down_payments = {}
                    for ci, p, _, cfg in group:
                        pct = (
                            cfg.down_payment_percentage
                            if cfg.down_payment_percentage is not None
                            else 100
                        )
                        item_dp = round(p.price * ci.quantity * (pct / 100.0), 2)
                        item_down_payments[ci.id] = item_dp
                    group_down_payment = sum(item_down_payments.values())
                    group_financed_amount = round(group_total - group_down_payment, 2)
                    group_status = "PENDING_VERIFICATION" if group_any_installments else "PENDING_VERIFICATION"
                else:
                    group_status = "PENDING_VERIFICATION"

                # Create order for this workshop
                order_entity = Order(
                    user_id=user_id,
                    vehicle_id=vehicle_id,
                    mileage=dto.mileage,
                    total_amount=group_total,
                    status=group_status,
                    delivery_method=wc.delivery_method,
                    delivery_address=wc.delivery_address,
                    reference_number=wc.reference_number,
                )
                order_model = await t.order.add(
                    self.__order_mapper.to_model(order_entity)
                )

                # Create order items
                for ci, p, w, cfg in group:
                    item_entity = OrderItem(
                        order_id=order_model.id,
                        part_id=ci.part_id,
                        workshop_id=p.workshop_id,
                        part_name=p.name,
                        quantity=ci.quantity,
                        unit_price=p.price,
                    )
                    await t.order_item.add(self.__item_mapper.to_model(item_entity))
                    p.stock -= ci.quantity
                    await t.part.update(p)

                # Create payments for this workshop
                if group_any_installments and group_financed_amount > 0:
                    # Si hay método de pago y referencia, registrar el pago inicial automáticamente
                    if wc.payment_method_id and wc.reference_number:
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=group_down_payment,
                            due_date=datetime.now(timezone.utc),  # El pago inicial tiene fecha actual
                            status="PENDING_VERIFICATION",
                            payment_method=str(wc.payment_method_id),
                            reference_number=wc.reference_number,
                        )
                    else:
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=group_down_payment,
                            due_date=datetime.now(timezone.utc),  # El pago inicial tiene fecha actual
                            status="PENDING",
                        )
                    await t.installment.add(inst_model)
                    installment_amount = round(group_financed_amount / 3, 2)
                    for i in range(3):
                        due = datetime.now(timezone.utc) + timedelta(days=15 * (i + 1))
                        # La última cuota absorbe cualquier diferencia por redondeo
                        if i == 2:
                            amount = round(group_financed_amount - (installment_amount * 2), 2)
                        else:
                            amount = installment_amount
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=amount,
                            due_date=due,
                            status="PENDING",
                        )
                        await t.installment.add(inst_model)
                else:
                    # Si hay método de pago y referencia, registrar el pago automáticamente
                    if wc.payment_method_id and wc.reference_number:
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=group_total,
                            due_date=datetime.now(timezone.utc),  # El pago de contado tiene fecha actual
                            status="PENDING_VERIFICATION",
                            payment_method=str(wc.payment_method_id),
                            reference_number=wc.reference_number,
                        )
                    else:
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=group_total,
                            due_date=datetime.now(timezone.utc),  # El pago de contado tiene fecha actual
                            status="PENDING",
                        )
                    await t.installment.add(inst_model)
                    for ci, p, w, _ in group:
                        log = VehicleHistoryLogModel(
                            vehicle_id=vehicle_id,
                            workshop_id=p.workshop_id,
                            log_date=datetime.now(timezone.utc),
                            mileage=dto.mileage,
                            description=f"Compra de {p.name} x{ci.quantity}",
                        )
                        await t.vehicle_history_log.add(log)

                created_orders.append(order_model)

            # Clear cart once
            for ci in cart.items:
                await t.cart._session.delete(ci)
            await t.cart._session.delete(cart)

            # Reload orders with installments
            loaded_orders = []
            for o in created_orders:
                loaded = await t.order.get_with_items(str(o.id))
                if loaded:
                    loaded_orders.append(loaded)

            return Response(
                status_code=201,
                success=True,
                message="Compra realizada exitosamente",
                content=OrderListDTO(
                    orders=[self._order_to_dto(o) for o in loaded_orders]
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
                content=OrderListDTO(orders=[self._order_to_dto(o) for o in orders]),
            )

    async def list_by_workshop(self, workshop_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            w_model = await t.workshop.get(str(workshop_id))
            if not w_model or w_model.owner_id != user_id:
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres el dueño de este taller",
                )

            orders = await t.order.list_by_workshop(str(workshop_id))

            def _ws_dto(o):
                client_rating = None; client_rated = False; workshop_rating = None; workshop_rated = False
                try:
                    for rvw in o.order_reviews:
                        if rvw.target_role == "WORKSHOP": client_rating = rvw.rating; client_rated = True
                        elif rvw.target_role == "CLIENT": workshop_rating = rvw.rating; workshop_rated = True
                except Exception: pass
                return WorkshopOrderDTO(
                    id=o.id, user_id=o.user_id, vehicle_id=o.vehicle_id, mileage=o.mileage,
                    total_amount=o.total_amount, status=o.status, delivery_method=o.delivery_method,
                    delivery_address=o.delivery_address, delivery_fee=o.delivery_fee,
                    reference_number=o.reference_number, confirmed_at=o.confirmed_at,
                    closed_by_client=bool(o.closed_by_client), closed_by_workshop=bool(o.closed_by_workshop),
                    items=[
                        OrderItemDTO(id=i.id, part_id=i.part_id, workshop_id=i.workshop_id,
                            part_name=i.part_name or "", quantity=i.quantity, unit_price=i.unit_price)
                        for i in o.items if i.workshop_id == workshop_id
                    ],
                    created_at=o.created_at,
                    ratings=OrderRatingInfo(client_rating=client_rating, client_rated=client_rated,
                        workshop_rating=workshop_rating, workshop_rated=workshop_rated),
                )

            return Response(
                status_code=200,
                success=True,
                content=WorkshopOrderListDTO(orders=[_ws_dto(o) for o in orders]),
            )

    async def get_installments(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
            installment=InstallmentRepository,
            workshop=WorkshopRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
            if not order_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden no encontrada",
                )

            # Allow buyer, workshop owner, or admin
            if order_model.user_id == user_id:
                pass  # buyer
            else:
                # Check if user is a workshop owner for any item in this order
                items = order_model.items
                item_workshop_ids = {str(i.workshop_id) for i in items}
                workshops_owned = await t.workshop.search(owner_id=str(user_id))
                workshop_ids = {str(w.id) for w in workshops_owned}
                is_owner = bool(workshop_ids.intersection(item_workshop_ids))

                # Check if user is admin
                stmt = select(UserRoleModel).where(
                    UserRoleModel.user_id == user_id,
                    UserRoleModel.role == "ADMIN",
                )
                r = await t.order._session.execute(stmt)
                is_admin = r.scalar_one_or_none() is not None

                if not is_owner and not is_admin:
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
                        order_id=inst.order_id,
                        amount=inst.amount,
                        due_date=inst.due_date,
                        payment_method=inst.payment_method,
                        reference_number=inst.reference_number,
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
            if inst_model.status == "PENDING_VERIFICATION":
                return Response(
                    status_code=400,
                    success=False,
                    message="Esta cuota ya tiene un pago pendiente de verificación",
                )

            inst_model.status = "PENDING_VERIFICATION"
            inst_model.payment_method = dto.payment_method
            inst_model.reference_number = dto.reference_number
            await t.installment.update(inst_model)

            # Get first workshop from order items for receiver
            stmt_items = select(OrderItemModel).where(
                OrderItemModel.order_id == order_model.id
            )
            r_items = await t.order._session.execute(stmt_items)
            first_item = r_items.scalars().first()
            receiver_workshop_id = first_item.workshop_id if first_item else None

            txn_model = TransactionModel(
                order_id=order_model.id,
                installment_id=inst_model.id,
                payer_user_id=user_id,
                receiver_workshop_id=receiver_workshop_id,
                amount=inst_model.amount,
                payment_method=dto.payment_method,
                status="PENDING",
            )
            await t.transaction.add(txn_model)

        return Response(
            status_code=200,
            success=True,
            message="Pago registrado, pendiente de verificación del taller",
            content=InstallmentDTO(
                id=inst_model.id,
                order_id=inst_model.order_id,
                amount=inst_model.amount,
                due_date=inst_model.due_date,
                payment_method=inst_model.payment_method,
                reference_number=inst_model.reference_number,
                status=inst_model.status,
                paid_at=inst_model.paid_at,
            ),
        )

    async def mark_installment_paid(
        self,
        installment_id: UUID,
        user_id: UUID,
        dto: MarkInstallmentPaidRequest,
    ) -> Response:
        async with self._transaction(
            order=OrderRepository,
            installment=InstallmentRepository,
            workshop=WorkshopRepository,
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

            order_model = await t.order.get_with_items(str(inst_model.order_id))
            if not order_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden no encontrada",
                )

            # Only workshop owner or admin can mark as paid
            items = order_model.items
            item_workshop_ids = {str(i.workshop_id) for i in items}
            workshops_owned = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = {str(w.id) for w in workshops_owned}
            is_owner = bool(workshop_ids.intersection(item_workshop_ids))

            stmt = select(UserRoleModel).where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role == "ADMIN",
            )
            r = await t.order._session.execute(stmt)
            is_admin = r.scalar_one_or_none() is not None

            if not is_owner and not is_admin:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes permisos para marcar cuotas como pagadas",
                )

            if inst_model.status == "PAID":
                return Response(
                    status_code=400,
                    success=False,
                    message="Esta cuota ya fue pagada",
                )

            inst_model.status = "PAID"
            # Si no tiene fecha de pago, establecer la fecha actual
            # Si ya tiene una fecha (del registro inicial), mantenerla
            if not inst_model.paid_at:
                inst_model.paid_at = datetime.now(timezone.utc)
            if dto.reference_number:
                inst_model.reference_number = dto.reference_number
            await t.installment.update(inst_model)

            # Update transaction to COMPLETED if exists
            txn_stmt = select(TransactionModel).where(
                TransactionModel.installment_id == inst_model.id
            )
            txn_r = await t.order._session.execute(txn_stmt)
            txn = txn_r.scalar_one_or_none()
            if txn:
                txn.status = "COMPLETED"
                await t.transaction.update(txn)

            # Check if all installments paid
            all_inst = await t.installment.list_by_order(str(order_model.id))
            if all(i.status == "PAID" for i in all_inst):
                # If order is already received, close it automatically
                if order_model.status == "RECEIVED":
                    order_model.status = "CLOSED"
                else:
                    order_model.status = "PAID"
                await t.order.update(order_model)

                # VehicleHistoryLog for each order item
                stmt_items = select(OrderItemModel).where(
                    OrderItemModel.order_id == order_model.id
                )
                ri = await t.order._session.execute(stmt_items)
                order_items = ri.scalars().all()
                for item in order_items:
                    p_stmt = select(PartModel).where(PartModel.id == item.part_id)
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
                message="Cuota marcada como pagada exitosamente",
                content=InstallmentDTO(
                    id=inst_model.id,
                    order_id=inst_model.order_id,
                    amount=inst_model.amount,
                    due_date=inst_model.due_date,
                    payment_method=inst_model.payment_method,
                    reference_number=inst_model.reference_number,
                    status=inst_model.status,
                    paid_at=inst_model.paid_at,
                ),
            )

    async def confirm_payment(
        self, order_id: UUID, user_id: UUID, dto: ConfirmPaymentRequest
    ) -> Response:
        async with self._transaction(
            order=OrderRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
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

            order_model.reference_number = dto.reference_number
            order_model.status = "PENDING_CONFIRMATION"
            await t.order.update(order_model)

            return Response(
                status_code=200,
                success=True,
                message="Referencia de pago registrada, pendiente de confirmación",
                content=self._order_to_dto(order_model),
            )

    async def confirm_received(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
            workshop=WorkshopRepository,
            order_item=OrderItemRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
            if not order_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden no encontrada",
                )

            items = order_model.items
            if not items:
                return Response(
                    status_code=400,
                    success=False,
                    message="La orden no tiene items",
                )

            # Check user owns at least one workshop that has items in this order
            workshops_owned = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = {str(w.id) for w in workshops_owned}
            item_workshop_ids = {str(i.workshop_id) for i in items}
            if not workshop_ids.intersection(item_workshop_ids):
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres dueño de los talleres en esta orden",
                )

            # Check that order status is PENDING_CONFIRMATION
            if order_model.status != "PENDING_CONFIRMATION":
                return Response(
                    status_code=400,
                    success=False,
                    message="La orden no está pendiente de confirmación",
                )

            order_model.confirmed_at = datetime.now(timezone.utc)
            # Set status based on installments
            installments = order_model.installments
            pending = [i for i in installments if i.status != "PAID"]

            if pending:
                order_model.status = "FINANCED"
            else:
                order_model.status = "PAID"

            await t.order.update(order_model)

            return Response(
                status_code=200,
                success=True,
                message="Pago confirmado exitosamente",
                content=self._order_to_dto(order_model),
            )

    async def mark_shipped(self, order_id: UUID, user_id: UUID, dto: MarkShippedRequest) -> Response:
        async with self._transaction(
            order=OrderRepository,
            workshop=WorkshopRepository,
            order_item=OrderItemRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
            if not order_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden no encontrada",
                )

            # Verify user is workshop owner
            items = order_model.items
            workshops_owned = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = {str(w.id) for w in workshops_owned}
            item_workshop_ids = {str(i.workshop_id) for i in items}
            if not workshop_ids.intersection(item_workshop_ids):
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres dueño de los talleres en esta orden",
                )

            # Check that order can be shipped (must be confirmed and paid/financed)
            if order_model.status not in ("PAID", "FINANCED"):
                return Response(
                    status_code=400,
                    success=False,
                    message="La orden debe estar confirmada y pagada para poder ser enviada",
                )

            # Check that delivery method is SHIPPING
            if order_model.delivery_method != "SHIPPING":
                return Response(
                    status_code=400,
                    success=False,
                    message="Esta orden no es para envío (método de entrega: PICKUP)",
                )

            order_model.status = "SHIPPED"
            order_model.tracking_number = dto.tracking_number
            order_model.shipping_notes = dto.shipping_notes
            order_model.shipped_at = datetime.now(timezone.utc)

            await t.order.update(order_model)

            return Response(
                status_code=200,
                success=True,
                message="Orden marcada como enviada exitosamente",
                content=self._order_to_dto(order_model),
            )

    async def get_by_id(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
            workshop=WorkshopRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
            if not order_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden no encontrada",
                )

            # Allow access if user is the buyer, a workshop owner in the order, or admin
            if order_model.user_id == user_id:
                return Response(
                    status_code=200,
                    success=True,
                    content=self._order_to_dto(order_model),
                )

            # Check if user owns a workshop that has items in this order
            items = order_model.items
            item_workshop_ids = {str(i.workshop_id) for i in items}
            workshops_owned = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = {str(w.id) for w in workshops_owned}
            if workshop_ids.intersection(item_workshop_ids):
                return Response(
                    status_code=200,
                    success=True,
                    content=self._order_to_dto(order_model),
                )

            # Check if admin
            stmt = select(UserRoleModel).where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role == "ADMIN",
            )
            r = await t.order._session.execute(stmt)
            if r.scalar_one_or_none() is not None:
                return Response(
                    status_code=200,
                    success=True,
                    content=self._order_to_dto(order_model),
                )

            return Response(
                status_code=403,
                success=False,
                message="No tienes acceso a esta orden",
            )

    async def list_by_all_workshops(self, user_id: UUID) -> Response:
        async with self._transaction(
            workshop=WorkshopRepository,
            order=OrderRepository,
        ) as t:
            workshops = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = [str(w.id) for w in workshops]

            all_orders = []
            for wid in workshop_ids:
                orders = await t.order.list_by_workshop(wid)
                for o in orders:
                    if o not in all_orders:
                        all_orders.append(o)

            all_orders.sort(key=lambda o: o.created_at, reverse=True)

            return Response(
                status_code=200,
                success=True,
                content=WorkshopOrderListDTO(
                    orders=[self._workshop_order_to_dto(o) for o in all_orders]
                ),
            )

    async def mark_received(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
            installment=InstallmentRepository,
            workshop=WorkshopRepository,
            vehicle_history_log=VehicleHistoryLogRepository,
            order_item=OrderItemRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
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
                    message="No eres el comprador de esta orden",
                )

            if order_model.status not in ("PAID", "FINANCED", "SHIPPED"):
                return Response(
                    status_code=400,
                    success=False,
                    message="El dueño del taller debe confirmar el pago primero",
                )

            order_model.closed_by_client = 1
            
            # Check if all installments are paid to auto-close
            installments = order_model.installments
            all_paid = all(i.status == "PAID" for i in installments)
            
            if all_paid:
                order_model.status = "CLOSED"
            elif order_model.closed_by_workshop:
                order_model.status = "CLOSED"
            
            await t.order.update(order_model)

            return Response(
                status_code=200,
                success=True,
                message="Orden marcada como recibida",
                content=self._order_to_dto(order_model),
            )

    async def mark_closed_by_workshop(self, order_id: UUID, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
            workshop=WorkshopRepository,
            order_item=OrderItemRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
            if not order_model:
                return Response(
                    status_code=404,
                    success=False,
                    message="Orden no encontrada",
                )

            items = order_model.items
            if not items:
                return Response(
                    status_code=400, success=False, message="La orden no tiene items"
                )

            workshops_owned = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = {str(w.id) for w in workshops_owned}
            item_workshop_ids = {str(i.workshop_id) for i in items}
            if not workshop_ids.intersection(item_workshop_ids):
                return Response(
                    status_code=403,
                    success=False,
                    message="No eres dueño de los talleres en esta orden",
                )

            order_model.closed_by_workshop = 1
            if order_model.closed_by_client:
                order_model.status = "CLOSED"
            await t.order.update(order_model)

            return Response(
                status_code=200,
                success=True,
                message="Orden cerrada por el taller",
                content=self._order_to_dto(order_model),
            )

    async def rate_order_workshop(
        self, order_id: UUID, user_id: UUID, dto: RateOrderRequest
    ) -> Response:
        async with self._transaction(
            order=OrderRepository,
            workshop=WorkshopRepository,
            order_item=OrderItemRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
            if not order_model:
                return Response(status_code=404, success=False, message="Orden no encontrada")

            if order_model.user_id != user_id:
                return Response(status_code=403, success=False, message="No eres el comprador de esta orden")

            if order_model.status != "CLOSED":
                return Response(status_code=400, success=False, message="La orden debe estar cerrada para calificar")

            # Get workshop id from items
            if not order_model.items:
                return Response(status_code=400, success=False, message="La orden no tiene items")
            workshop_id = order_model.items[0].workshop_id

            # Check existing review
            stmt = select(OrderReviewModel).where(
                OrderReviewModel.order_id == order_model.id,
                OrderReviewModel.rater_id == user_id,
            )
            existing = (await t.order._session.execute(stmt)).scalar_one_or_none()
            if existing:
                return Response(status_code=400, success=False, message="Ya calificaste esta orden")

            review = OrderReviewModel(
                order_id=order_model.id,
                workshop_id=workshop_id,
                rater_id=user_id,
                target_role="WORKSHOP",
                rating=dto.rating,
                comment=dto.comment,
            )
            t.order._session.add(review)
            await t.order._session.flush()

            # Update workshop average_rating
            from sqlalchemy import func as sa_func
            avg = await t.order._session.execute(
                select(sa_func.avg(OrderReviewModel.rating)).where(
                    OrderReviewModel.workshop_id == workshop_id,
                    OrderReviewModel.target_role == "WORKSHOP",
                )
            )
            w_model = await t.workshop.get(str(workshop_id))
            if w_model:
                w_model.average_rating = round(avg.scalar() or dto.rating, 1)
                await t.workshop.update(w_model)

            return Response(
                status_code=200,
                success=True,
                message="Calificación registrada exitosamente",
                content=self._order_to_dto(order_model),
            )

    async def rate_order_client(
        self, order_id: UUID, user_id: UUID, dto: RateOrderRequest
    ) -> Response:
        async with self._transaction(
            order=OrderRepository,
            workshop=WorkshopRepository,
            order_item=OrderItemRepository,
        ) as t:
            order_model = await t.order.get_with_items(str(order_id))
            if not order_model:
                return Response(status_code=404, success=False, message="Orden no encontrada")

            if order_model.status != "CLOSED":
                return Response(status_code=400, success=False, message="La orden debe estar cerrada para calificar")

            # Verify user is workshop owner
            items = order_model.items
            workshops_owned = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = {str(w.id) for w in workshops_owned}
            item_workshop_ids = {str(i.workshop_id) for i in items}
            if not workshop_ids.intersection(item_workshop_ids):
                return Response(status_code=403, success=False, message="No eres dueño de los talleres en esta orden")

            workshop_id = items[0].workshop_id

            # Check existing review
            stmt = select(OrderReviewModel).where(
                OrderReviewModel.order_id == order_model.id,
                OrderReviewModel.rater_id == user_id,
            )
            existing = (await t.order._session.execute(stmt)).scalar_one_or_none()
            if existing:
                return Response(status_code=400, success=False, message="Ya calificaste esta orden")

            review = OrderReviewModel(
                order_id=order_model.id,
                workshop_id=workshop_id,
                rater_id=user_id,
                target_role="CLIENT",
                rating=dto.rating,
                comment=dto.comment,
            )
            t.order._session.add(review)
            await t.order._session.flush()

            return Response(
                status_code=200,
                success=True,
                message="Calificación registrada exitosamente",
                content=self._order_to_dto(order_model),
            )

    def _order_to_dto(self, o: OrderModel) -> OrderDTO:
        first_workshop_name = None
        first_workshop_id = None
        if o.items:
            first_item = o.items[0]
            first_workshop_name = (
                first_item.part.workshop.name
                if first_item.part and first_item.part.workshop
                else None
            )
            first_workshop_id = (
                str(first_item.workshop_id) if first_item.workshop_id else None
            )

        try:
            installment_count = len(o.installments) if o.installments else 0
        except Exception:
            installment_count = 0

        # Extract rating info from order_reviews
        client_rating = None
        client_rated = False
        workshop_rating = None
        workshop_rated = False
        try:
            for rvw in o.order_reviews:
                if rvw.target_role == "WORKSHOP":
                    client_rating = rvw.rating
                    client_rated = True
                elif rvw.target_role == "CLIENT":
                    workshop_rating = rvw.rating
                    workshop_rated = True
        except Exception:
            pass

        return OrderDTO(
            id=o.id,
            vehicle_id=o.vehicle_id,
            total_amount=o.total_amount,
            down_payment=0.0,
            financed_amount=0.0,
            installment_count=installment_count,
            status=o.status,
            delivery_method=o.delivery_method,
            delivery_address=o.delivery_address,
            delivery_fee=o.delivery_fee,
            reference_number=o.reference_number,
            tracking_number=o.tracking_number,
            shipping_notes=o.shipping_notes,
            shipped_at=o.shipped_at,
            workshop_name=first_workshop_name,
            workshop_id=first_workshop_id,
            closed_by_client=bool(o.closed_by_client),
            closed_by_workshop=bool(o.closed_by_workshop),
            items=[
                OrderItemDTO(
                    id=i.id,
                    part_id=i.part_id,
                    workshop_id=i.workshop_id,
                    part_name=i.part_name
                    or (i.part.name if hasattr(i, "part") and i.part else ""),
                    quantity=i.quantity,
                    unit_price=i.unit_price,
                )
                for i in o.items
            ],
            created_at=o.created_at,
            ratings=OrderRatingInfo(
                client_rating=client_rating,
                client_rated=client_rated,
                workshop_rating=workshop_rating,
                workshop_rated=workshop_rated,
            ),
        )

    def _workshop_order_to_dto(self, o: OrderModel) -> WorkshopOrderDTO:
        client_rating = None
        client_rated = False
        workshop_rating = None
        workshop_rated = False
        try:
            for rvw in o.order_reviews:
                if rvw.target_role == "WORKSHOP":
                    client_rating = rvw.rating
                    client_rated = True
                elif rvw.target_role == "CLIENT":
                    workshop_rating = rvw.rating
                    workshop_rated = True
        except Exception:
            pass
        return WorkshopOrderDTO(
            id=o.id,
            user_id=o.user_id,
            vehicle_id=o.vehicle_id,
            mileage=o.mileage,
            total_amount=o.total_amount,
            status=o.status,
            delivery_method=o.delivery_method,
            delivery_address=o.delivery_address,
            delivery_fee=o.delivery_fee,
            reference_number=o.reference_number,
            confirmed_at=o.confirmed_at,
            closed_by_client=bool(o.closed_by_client),
            closed_by_workshop=bool(o.closed_by_workshop),
            items=[
                OrderItemDTO(
                    id=i.id,
                    part_id=i.part_id,
                    workshop_id=i.workshop_id,
                    part_name=i.part_name or "",
                    quantity=i.quantity,
                    unit_price=i.unit_price,
                )
                for i in o.items
            ],
            created_at=o.created_at,
            ratings=OrderRatingInfo(
                client_rating=client_rating,
                client_rated=client_rated,
                workshop_rating=workshop_rating,
                workshop_rated=workshop_rated,
            ),
        )


def get_order_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> OrderService:
    return OrderService(transaction)
