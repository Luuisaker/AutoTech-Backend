import math
import logging
from typing import Type, Any
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import Depends

logger = logging.getLogger(__name__)

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID
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
from src.modules.users.infrastructure.repository import UserRepository
from src.modules.credit.infrastructure.repository import CreditLevelRepository, CreditHistoryRepository, LateFeeRepository
from src.modules.credit.infrastructure.service import CreditService
from src.config.models import (
    Installment as InstallmentModel,
    Transaction as TransactionModel,
    VehicleHistoryLog as VehicleHistoryLogModel,
    Order as OrderModel,
    OrderItem as OrderItemModel,
    Part as PartModel,
    UserRole as UserRoleModel,
    OrderReview as OrderReviewModel,
    WorkshopCommission as WorkshopCommissionModel,
    User as UserModel,
)
from src.modules.parts.infrastructure.repository import (
    VehicleHistoryLogRepository,
)
from sqlalchemy import select, update as sql_update


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
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            # Block checkout if user has any open mora
            late_fee_repo = LateFeeRepository(t.order._session)
            open_moras = await late_fee_repo.list_open_by_user(user_id)
            if open_moras:
                return Response(
                    status_code=400,
                    success=False,
                    message="Tienes moras pendientes. Paga primero las moras antes de realizar compras.",
                )

            # Get vehicle (optional - not required for parts checkout)
            vehicle_id = dto.vehicle_id
            if vehicle_id:
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
                if not w_model or not w_model.is_certified or w_model.is_suspended:
                    return Response(
                        status_code=400,
                        success=False,
                        message=f"El taller de {p_model.name} no está disponible",
                    )
                if w_model.commission_suspended:
                    return Response(
                        status_code=403,
                        success=False,
                        message=f"El taller de {p_model.name} tiene comisiones impagas y está suspendido temporalmente.",
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

            # --- Calculate total financed ---
            total_financed_parts = 0.0
            for wid, group in workshop_groups.items():
                for ci, p, _, cfg in group:
                    pct = (
                        cfg.down_payment_percentage
                        if cfg.down_payment_percentage is not None
                        else 100
                    )
                    if pct < 100:
                        item_total = p.price * ci.quantity
                        financed = round(item_total - (item_total * pct / 100.0), 2)
                        total_financed_parts += financed

            # --- Credit validation via CreditService ---
            if total_financed_parts > 0:
                user_model = await t.user.get(str(user_id))
                if not user_model:
                    return Response(
                        status_code=400,
                        success=False,
                        message="Usuario no encontrado",
                    )

                # Check workshop commission debt (financing pause)
                now = datetime.now(timezone.utc)
                current_month = now.month
                current_year = now.year
                for wid in workshop_groups:
                    comm_stmt = select(WorkshopCommissionModel).where(
                        WorkshopCommissionModel.workshop_id == wid,
                        WorkshopCommissionModel.status == "PENDING",
                    )
                    # Unpaid commissions from previous months
                    comm_stmt = comm_stmt.where(
                        (WorkshopCommissionModel.period_year < current_year) |
                        (
                            (WorkshopCommissionModel.period_year == current_year) &
                            (WorkshopCommissionModel.period_month < current_month)
                        )
                    )
                    r = await t.user._session.execute(comm_stmt)
                    unpaid = r.scalars().all()
                    if unpaid:
                        total_debt = sum(c.commission_amount for c in unpaid)
                        # Auto-suspend workshop for unpaid commissions
                        ws_to_suspend = await t.workshop.get(wid)
                        if ws_to_suspend:
                            ws_to_suspend.commission_suspended = 1
                            ws_to_suspend.is_suspended = 1
                            await t.workshop.update(ws_to_suspend)
                        return Response(
                            status_code=403,
                            success=False,
                            message=(
                                f"El taller tiene comisiones pendientes de ${total_debt:.2f} "
                                f"de meses anteriores. El financiamiento está pausado hasta que se regularice."
                            ),
                        )

                # Calculate current parts debt dynamically from unpaid installments
                from src.config.models import Installment as ChkInst, Order as ChkOrd
                from sqlalchemy import func as sql_func
                debt_stmt = (
                    select(sql_func.coalesce(sql_func.sum(ChkInst.amount), 0.0))
                    .join(ChkOrd, ChkInst.order_id == ChkOrd.id)
                    .where(
                        ChkOrd.user_id == user_id,
                        ChkInst.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                        ChkInst.deleted_at.is_(None),
                        ChkOrd.deleted_at.is_(None),
                    )
                )
                debt_r = await t.user._session.execute(debt_stmt)
                current_parts_debt = round(debt_r.scalar() or 0.0, 2)

                parts_available = user_model.parts_credit_limit - current_parts_debt
                if total_financed_parts > parts_available:
                    needed_dp_pct = ((total_financed_parts - parts_available) / total_financed_parts) * 100
                    suggested_dp = math.ceil(needed_dp_pct) + 10
                    return Response(
                        status_code=400,
                        success=False,
                        message=(
                            f"Tu límite de crédito disponible es ${parts_available:.2f}. "
                            f"Necesitas un pago inicial de al menos {suggested_dp}% "
                            f"para financiar esta compra."
                        ),
                        min_down_payment_percentage=suggested_dp,
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
                            else p.installment_min_percentage or 20
                        )
                        item_dp = round(p.price * ci.quantity * (pct / 100.0), 2)
                        item_down_payments[ci.id] = item_dp
                    group_down_payment = sum(item_down_payments.values())
                    group_financed_amount = round(group_total - group_down_payment, 2)
                    group_status = "PENDING_VERIFICATION" if group_any_installments else "PENDING"
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
                    # Calculate identical installments; remainder goes to down payment
                    installment_amount = round(group_financed_amount / 3, 2)
                    remainder = round(group_financed_amount - (installment_amount * 3), 2)
                    adjusted_down_payment = round(group_down_payment + remainder, 2)

                    # Si hay método de pago y referencia, registrar el pago inicial automáticamente
                    if wc.payment_method_id and wc.reference_number:
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=adjusted_down_payment,
                            due_date=datetime.now(timezone.utc),  # El pago inicial tiene fecha actual
                            status="PENDING_VERIFICATION",
                            payment_method=str(wc.payment_method_id),
                            reference_number=wc.reference_number,
                        )
                    else:
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=adjusted_down_payment,
                            due_date=datetime.now(timezone.utc),  # El pago inicial tiene fecha actual
                            status="PENDING",
                        )
                    await t.installment.add(inst_model)
                    for i in range(3):
                        due = datetime.now(timezone.utc) + timedelta(days=15 * (i + 1))
                        inst_model = InstallmentModel(
                            order_id=order_model.id,
                            amount=installment_amount,
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
                        if vehicle_id:
                            log = VehicleHistoryLogModel(
                                vehicle_id=vehicle_id,
                                workshop_id=p.workshop_id,
                                log_date=datetime.now(timezone.utc),
                                mileage=dto.mileage,
                                description=f"Compra de {p.name} x{ci.quantity}",
                            )
                            await t.vehicle_history_log.add(log)

                created_orders.append(order_model)

                # Create commission record for ALL orders (5% of total order amount)
                commission_amount = round(group_total * 0.05, 2)
                now_dt = datetime.now(timezone.utc)
                commission = WorkshopCommissionModel(
                    workshop_id=wid,
                    order_id=order_model.id,
                    financed_amount=group_total,
                    commission_rate=5.0,
                    commission_amount=commission_amount,
                    period_month=now_dt.month,
                    period_year=now_dt.year,
                    status="PENDING",
                )
                t.order._session.add(commission)
                await t.order._session.flush()

            # --- Record credit history (debt is calculated dynamically from installments) ---
            if total_financed_parts > 0:
                await t.credit_history.add_entry(
                    user_id=user_id,
                    type="PURCHASE",
                    amount=total_financed_parts,
                    parts_line_used=total_financed_parts,
                    description=f"Financiamiento de compra: ${total_financed_parts:.2f}",
                )

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

            # Capture email data before session closes
            _email_order_data = []
            for o in loaded_orders:
                ws_name = "AutoTech"
                if o.items:
                    from src.config.models import Workshop as _WM
                    _ws = await t.order._session.get(_WM, o.items[0].workshop_id)
                    ws_name = _ws.name if _ws else "AutoTech"
                insts = o.installments or []
                _email_order_data.append({
                    "order_id": str(o.id),
                    "workshop_name": ws_name,
                    "total": o.total_amount,
                    "down_payment": insts[0].amount if insts else o.total_amount,
                    "financed": sum(i.amount for i in insts[1:]) if len(insts) > 1 else 0,
                    "installment_count": len(insts),
                    "installment_schedule": [
                        {
                            "amount": inst.amount,
                            "due_date": inst.due_date.strftime("%d/%m/%Y") if inst.due_date else "N/A",
                            "status": inst.status,
                            "paid_at": inst.paid_at.strftime("%d/%m/%Y") if inst.paid_at else None,
                        }
                        for inst in insts
                    ],
                })

            _result = Response(
                status_code=201,
                success=True,
                message="Compra realizada exitosamente",
                content=OrderListDTO(
                    orders=[self._order_to_dto(o) for o in loaded_orders]
                ),
            )

        # Send purchase confirmation email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import purchase_confirmation
            from src.config.database import get_session
            from src.config.models import User as _UM
            async with get_session() as _sess:
                _u_stmt = select(_UM).where(_UM.id == user_id)
                _u = (await _sess.execute(_u_stmt)).scalars().first()
                if _u:
                    for ed in _email_order_data:
                        await send_email(
                            _u.email,
                            "Compra realizada - AutoTech",
                            purchase_confirmation(
                                buyer_name=_u.first_name,
                                order_id=ed["order_id"],
                                workshop_name=ed["workshop_name"],
                                total=ed["total"],
                                down_payment=ed["down_payment"],
                                financed=ed["financed"],
                                installment_count=ed["installment_count"],
                                installment_schedule=ed.get("installment_schedule"),
                                lang=_u.language_preference or "es",
                            ),
                        )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send purchase confirmation email: {e}", exc_info=True)

        return _result

    async def list_mine(self, user_id: UUID) -> Response:
        async with self._transaction(
            order=OrderRepository,
        ) as t:
            orders = await t.order.list_by_user(str(user_id))
            # Sort: pending orders by earliest pending installment due_date first
            def sort_key(o):
                pending_insts = [i for i in (o.installments or []) if i.status in ("PENDING", "PENDING_VERIFICATION")]
                if pending_insts:
                    earliest = min(i.due_date for i in pending_insts)
                    return (0, earliest)
                return (1, o.created_at)
            orders = sorted(orders, key=sort_key)
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
                    has_pending_verification=any(
                        inst.status == "PENDING_VERIFICATION" for inst in o.installments
                    ),
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
                    UserRoleModel.role_id == ROLE_NAME_TO_UUID["ADMIN"],
                )
                r = await t.order._session.execute(stmt)
                is_admin = r.scalars().first() is not None

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
            # Block payment if user has any open mora
            late_fee_repo = LateFeeRepository(t.order._session)
            open_moras = await late_fee_repo.list_open_by_user(user_id)
            if open_moras:
                return Response(
                    status_code=400,
                    success=False,
                    message="Tienes moras pendientes. Paga primero las moras antes de pagar cuotas.",
                )

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

            # Validate payment date is not before order creation date
            if dto.paid_at:
                payment_date = dto.paid_at if isinstance(dto.paid_at, datetime) else datetime.fromisoformat(str(dto.paid_at))
                if payment_date.replace(tzinfo=timezone.utc) < order_model.created_at:
                    return Response(
                        status_code=400,
                        success=False,
                        message="La fecha de pago no puede ser anterior a la fecha de creación de la orden.",
                    )

            inst_model.status = "PENDING_VERIFICATION"
            inst_model.payment_method = dto.payment_method
            inst_model.reference_number = dto.reference_number
            inst_model.rate = dto.rate
            inst_model.rate_date = dto.rate_date
            if dto.paid_at:
                inst_model.paid_at = dto.paid_at
            # If no rate provided, fetch BCV rate for the payment date
            if inst_model.rate is None and inst_model.paid_at:
                from src.modules.orders.infrastructure.bcv import get_bcv_rate_for_date
                rate_info = await get_bcv_rate_for_date(inst_model.paid_at)
                if rate_info:
                    inst_model.rate = rate_info.usd
                    inst_model.rate_date = rate_info.date
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
                rate=inst_model.rate,
                rate_date=inst_model.rate_date,
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
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
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
                UserRoleModel.role_id == ROLE_NAME_TO_UUID["ADMIN"],
            )
            r = await t.order._session.execute(stmt)
            is_admin = r.scalars().first() is not None

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
            # Use provided paid_at, or keep existing, or use now
            if dto.paid_at:
                inst_model.paid_at = dto.paid_at
            elif not inst_model.paid_at:
                inst_model.paid_at = datetime.now(timezone.utc)
            if dto.reference_number:
                inst_model.reference_number = dto.reference_number
            
            # Si no tiene tasa BCV, obtener la histórica para la fecha de pago
            if inst_model.rate is None:
                from src.modules.orders.infrastructure.bcv import get_bcv_rate_for_date
                rate_info = await get_bcv_rate_for_date(inst_model.paid_at)
                if rate_info:
                    inst_model.rate = rate_info.usd
                    inst_model.rate_date = rate_info.date
            
            await t.installment.update(inst_model)

            # Update transaction to COMPLETED if exists
            txn_stmt = select(TransactionModel).where(
                TransactionModel.installment_id == inst_model.id
            ).order_by(TransactionModel.created_at.desc()).limit(1)
            txn_r = await t.order._session.execute(txn_stmt)
            txn = txn_r.scalars().first()
            if txn:
                txn.status = "COMPLETED"
                await t.transaction.update(txn)

            # Update order status based on installment payment progress
            all_inst = await t.installment.list_by_order(str(order_model.id))
            all_paid = all(i.status == "PAID" for i in all_inst)
            any_paid = any(i.status == "PAID" for i in all_inst)

            if all_paid:
                # If order is already received/shipped, close it automatically
                if order_model.status in ("RECEIVED", "SHIPPED"):
                    order_model.status = "CLOSED"
                else:
                    order_model.status = "PAID"
                await t.order.update(order_model)

                # VehicleHistoryLog for each order item (only if vehicle assigned)
                if order_model.vehicle_id:
                    stmt_items = select(OrderItemModel).where(
                        OrderItemModel.order_id == order_model.id
                    )
                    ri = await t.order._session.execute(stmt_items)
                    order_items = ri.scalars().all()
                    for item in order_items:
                        p_stmt = select(PartModel).where(PartModel.id == item.part_id)
                        pr = await t.order._session.execute(p_stmt)
                        p_model = pr.scalars().first()
                        log = VehicleHistoryLogModel(
                            vehicle_id=order_model.vehicle_id,
                        workshop_id=p_model.workshop_id if p_model else None,
                        log_date=datetime.now(timezone.utc),
                        mileage=order_model.mileage,
                        description="Compra de repuesto completada",
                    )
                    await t.vehicle_history_log.add(log)

            elif any_paid and order_model.status in ("PENDING_VERIFICATION", "PENDING_CONFIRMATION"):
                order_model.status = "FINANCED"
                await t.order.update(order_model)

            # --- Credit: add points, recalculate level (debt is dynamic) ---
            order_user = await t.user.get(str(order_model.user_id))
            if order_user:

                # 1. Revert mora: find open late fee for this installment → WAIVED
                late_fee_repo = LateFeeRepository(t.order._session)
                open_mora = await late_fee_repo.find_open_by_installment(inst_model.id, "PARTS")
                if open_mora:
                    open_mora.status = "WAIVED"
                    t.order._session.add(open_mora)
                    await t.order._session.flush()
                    await t.credit_history.add_entry(
                        user_id=order_model.user_id,
                        type="LATE_FEE_WAIVED",
                        amount=open_mora.amount,
                        description=f"Mora revertida por pago de cuota: ${open_mora.amount:.2f}",
                        reference_id=open_mora.id,
                    )

                # 2. Recover penalty points: sum PENALTY entries for this installment
                penalty_entries = await late_fee_repo.find_penalty_history_by_installment(inst_model.id)
                recovered_points = sum(abs(e.amount) for e in penalty_entries)
                if recovered_points > 0:
                    order_user.credit_points = round(order_user.credit_points + recovered_points, 2)
                    await t.credit_history.add_entry(
                        user_id=order_model.user_id,
                        type="POINTS_RESTORED",
                        amount=recovered_points,
                        description=f"Puntos restaurados por pago de cuota atrasada: +{recovered_points:.2f}",
                        reference_id=inst_model.id,
                    )

                # 3. Points on time: if paid_at <= due_date, grant inst.amount points
                # For the initial installment (first one created at checkout), use
                # order.created_at as reference instead of due_date, since due_date = now
                # at checkout time and the workshop verifies later, making paid_at > due_date.
                paid_at = inst_model.paid_at
                if paid_at and paid_at.tzinfo is None:
                    paid_at = paid_at.replace(tzinfo=timezone.utc)
                all_inst_for_ref = await t.installment.list_by_order(str(order_model.id))
                all_inst_sorted = sorted(all_inst_for_ref, key=lambda x: x.created_at)
                is_initial = len(all_inst_sorted) > 0 and inst_model.id == all_inst_sorted[0].id
                if is_initial:
                    ref_date = order_model.created_at
                    if ref_date and ref_date.tzinfo is None:
                        ref_date = ref_date.replace(tzinfo=timezone.utc)
                    is_on_time = paid_at is None or paid_at <= ref_date + timedelta(hours=48)
                else:
                    due_date = inst_model.due_date
                    if due_date and due_date.tzinfo is None:
                        due_date = due_date.replace(tzinfo=timezone.utc)
                    is_on_time = paid_at is None or paid_at <= due_date
                if is_on_time:
                    order_user.credit_points = round(order_user.credit_points + inst_model.amount, 2)
                    logger.info(f"Credit points +{inst_model.amount} for user {order_user.id} (initial={is_initial}, on_time). Total: {order_user.credit_points}")
                else:
                    logger.info(f"Credit points NOT added for installment {inst_model.id} (initial={is_initial}, paid_at={paid_at}, due_date={inst_model.due_date})")

                await t.user.update(order_user)
                await t.credit_history.add_entry(
                    user_id=order_model.user_id,
                    type="PAYMENT",
                    amount=inst_model.amount,
                    parts_line_used=inst_model.amount,
                    description=f"Cuota pagada{' a tiempo' if is_on_time else ' tarde'}: ${inst_model.amount:.2f}",
                    reference_id=inst_model.id,
                )
                # Recalculate level
                credit_svc = CreditService.__new__(CreditService)
                await credit_svc.recalculate_level(t.user._session, order_user)

            # Capture data for email before session closes
            _email_order_id = str(order_model.id)
            _email_order_user_id = order_model.user_id
            _email_inst_amount = inst_model.amount
            _email_inst_id = inst_model.id
            _email_order_became_paid = order_model.status in ("PAID", "CLOSED")
            _email_order_total = order_model.total_amount
            _email_workshop_name = "AutoTech"
            if order_model.items:
                from src.config.models import Workshop as _WM2
                _ws2 = await t.order._session.get(_WM2, order_model.items[0].workshop_id)
                _email_workshop_name = _ws2.name if _ws2 else "AutoTech"

            _result = Response(
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
                    rate=inst_model.rate,
                    rate_date=inst_model.rate_date,
                ),
            )

        # Send installment verified email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import installment_verified
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, Installment as _IM
            async with _gs() as _sess:
                _u_stmt = select(_UM).where(_UM.id == _email_order_user_id)
                _u = (await _sess.execute(_u_stmt)).scalars().first()
                _inst_stmt = select(_IM).where(_IM.order_id == _email_order_id, _IM.deleted_at.is_(None))
                _all_insts = list((await _sess.execute(_inst_stmt)).scalars().all())
                _inst_num = next((i for i, inst in enumerate(_all_insts) if str(inst.id) == str(_email_inst_id)), -1) + 1
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
                            order_id=_email_order_id,
                            installment_number=_inst_num,
                            amount=_email_inst_amount,
                            next_due_date=_next.due_date.strftime("%d/%m/%Y") if _next else None,
                            schedule=_schedule,
                            lang=_u.language_preference or "es",
                        ),
                    )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send installment verified email: {e}", exc_info=True)

        # Send order fully paid email if all installments are now paid
        if _email_order_became_paid:
            try:
                from src.utils.email_templates import order_fully_paid
                async with _gs() as _sess:
                    _u_stmt = select(_UM).where(_UM.id == _email_order_user_id)
                    _u = (await _sess.execute(_u_stmt)).scalars().first()
                    if _u:
                        await send_email(
                            _u.email,
                            "Orden completamente pagada - AutoTech",
                            order_fully_paid(
                                buyer_name=_u.first_name,
                                order_id=_email_order_id,
                                workshop_name=_email_workshop_name,
                                total=_email_order_total,
                                lang=_u.language_preference or "es",
                            ),
                        )
            except Exception as e:
                import logging
                logging.warning(f"Failed to send order fully paid email: {e}", exc_info=True)

        return _result

    async def mark_installment_erroneous(
        self,
        installment_id: UUID,
        user_id: UUID,
    ) -> Response:
        async with self._transaction(
            order=OrderRepository,
            installment=InstallmentRepository,
            workshop=WorkshopRepository,
            transaction=TransactionRepository,
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
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

            # Only workshop owner or admin can mark as erroneous
            items = order_model.items
            item_workshop_ids = {str(i.workshop_id) for i in items}
            workshops_owned = await t.workshop.search(owner_id=str(user_id))
            workshop_ids = {str(w.id) for w in workshops_owned}
            is_owner = bool(workshop_ids.intersection(item_workshop_ids))

            stmt = select(UserRoleModel).where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id == ROLE_NAME_TO_UUID["ADMIN"],
            )
            r = await t.order._session.execute(stmt)
            is_admin = r.scalars().first() is not None

            if not is_owner and not is_admin:
                return Response(
                    status_code=403,
                    success=False,
                    message="No tienes permisos para marcar cuotas como erróneas",
                )

            if inst_model.status not in ("PAID", "PENDING_VERIFICATION"):
                return Response(
                    status_code=400,
                    success=False,
                    message="Solo se pueden marcar como erróneas las cuotas pagadas o pendientes de verificación",
                )

            # Capture original state before reverting
            original_paid_at = inst_model.paid_at
            original_status = inst_model.status

            # Revert installment to PENDING
            inst_model.status = "PENDING"
            inst_model.paid_at = None
            await t.installment.update(inst_model)

            # Revert any open mora (late fee) for this installment back to PENDING
            late_fee_repo = LateFeeRepository(t.order._session)
            open_mora = await late_fee_repo.find_open_by_installment(inst_model.id, "PARTS")
            if open_mora:
                open_mora.status = "PENDING"
                open_mora.payment_method = "OTHER"
                open_mora.reference_number = None
                open_mora.paid_at = None
                t.order._session.add(open_mora)
                await t.order._session.flush()

            # Revert transaction status
            txn_stmt = select(TransactionModel).where(
                TransactionModel.installment_id == inst_model.id
            ).order_by(TransactionModel.created_at.desc()).limit(1)
            txn_r = await t.order._session.execute(txn_stmt)
            txn = txn_r.scalars().first()
            if txn:
                txn.status = "REVERTED"
                await t.transaction.update(txn)

            # Revert order status if it was PAID/CLOSED
            all_inst = await t.installment.list_by_order(str(order_model.id))
            if not all(i.status == "PAID" for i in all_inst):
                if order_model.status in ("PAID", "CLOSED"):
                    if order_model.status == "CLOSED":
                        order_model.status = "RECEIVED"
                    else:
                        order_model.status = "PENDING_VERIFICATION"
                    await t.order.update(order_model)

            # Revert credit: remove points (debt is dynamic from installments)
            # Only revert points if the installment was actually PAID (points are awarded on mark_paid, not on registration)
            order_user = await t.user.get(str(order_model.user_id))
            if order_user and original_status == "PAID":
                # Remove the points that were awarded for this payment
                # Points awarded = inst.amount if on-time, 0 if late
                _orig_paid_at = original_paid_at
                if _orig_paid_at and _orig_paid_at.tzinfo is None:
                    _orig_paid_at = _orig_paid_at.replace(tzinfo=timezone.utc)
                _due_date = inst_model.due_date
                if _due_date and _due_date.tzinfo is None:
                    _due_date = _due_date.replace(tzinfo=timezone.utc)
                was_on_time = _orig_paid_at is None or _orig_paid_at <= _due_date
                points_to_remove = inst_model.amount if was_on_time else 0
                if points_to_remove > 0:
                    order_user.credit_points = max(0.0, round(order_user.credit_points - points_to_remove, 2))

                await t.user.update(order_user)
                await t.credit_history.add_entry(
                    user_id=order_model.user_id,
                    type="PAYMENT_REVERTED",
                    amount=inst_model.amount,
                    parts_line_used=inst_model.amount,
                    description=f"Cuota revertida por pago erróneo: ${inst_model.amount:.2f}",
                    reference_id=inst_model.id,
                )
                credit_svc = CreditService.__new__(CreditService)
                await credit_svc.recalculate_level(t.user._session, order_user)

            # Capture data for email before session closes
            _email_order_id = str(order_model.id)
            _email_order_user_id = order_model.user_id
            _email_inst_amount = inst_model.amount
            _email_inst_id = inst_model.id

            _result = Response(
                status_code=200,
                success=True,
                message="Cuota marcada como errónea",
                content=InstallmentDTO(
                    id=inst_model.id,
                    order_id=inst_model.order_id,
                    amount=inst_model.amount,
                    due_date=inst_model.due_date,
                    payment_method=inst_model.payment_method,
                    reference_number=inst_model.reference_number,
                    status=inst_model.status,
                    paid_at=inst_model.paid_at,
                    rate=inst_model.rate,
                    rate_date=inst_model.rate_date,
                ),
            )

        # Send installment rejected email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import installment_rejected
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, Installment as _IM
            async with _gs() as _sess:
                _u_stmt = select(_UM).where(_UM.id == _email_order_user_id)
                _u = (await _sess.execute(_u_stmt)).scalars().first()
                _inst_stmt = select(_IM).where(_IM.order_id == _email_order_id, _IM.deleted_at.is_(None))
                _all_insts = list((await _sess.execute(_inst_stmt)).scalars().all())
                _inst_num = next((i for i, inst in enumerate(_all_insts) if str(inst.id) == str(_email_inst_id)), -1) + 1
                if _inst_num == 0:
                    _inst_num = 1
                if _u:
                    await send_email(
                        _u.email,
                        "Pago rechazado - AutoTech",
                        installment_rejected(
                            buyer_name=_u.first_name,
                            order_id=_email_order_id,
                            installment_number=_inst_num,
                            amount=_email_inst_amount,
                            lang=_u.language_preference or "es",
                        ),
                    )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send installment rejected email: {e}", exc_info=True)

        return _result

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

            # Auto-close if all installments already paid
            installments = order_model.installments
            if installments and all(i.status == "PAID" for i in installments):
                order_model.status = "CLOSED"

            await t.order.update(order_model)

            # Capture data for email before session closes
            _email_order_id = str(order_model.id)
            _email_order_user_id = order_model.user_id

            _result = Response(
                status_code=200,
                success=True,
                message="Orden marcada como enviada exitosamente",
                content=self._order_to_dto(order_model),
            )

        # Send order shipped email (outside transaction)
        try:
            from src.utils.email import send_email
            from src.utils.email_templates import order_shipped
            from src.config.database import get_session as _gs
            from src.config.models import User as _UM, Workshop as _WM, OrderItem as _OIM
            async with _gs() as _sess:
                _u_stmt = select(_UM).where(_UM.id == _email_order_user_id)
                _u = (await _sess.execute(_u_stmt)).scalars().first()
                _ws_stmt = select(_WM.name).join(_OIM, _OIM.workshop_id == _WM.id).where(_OIM.order_id == _email_order_id).limit(1)
                _ws_name = (await _sess.execute(_ws_stmt)).scalar() or "AutoTech"
                if _u:
                    await send_email(
                        _u.email,
                        "Orden enviada - AutoTech",
                        order_shipped(
                            buyer_name=_u.first_name,
                            order_id=_email_order_id,
                            workshop_name=_ws_name,
                            tracking_number=dto.tracking_number,
                            shipping_notes=dto.shipping_notes,
                            lang=_u.language_preference or "es",
                        ),
                    )
        except Exception as e:
            import logging
            logging.warning(f"Failed to send order shipped email: {e}", exc_info=True)

        return _result

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
                UserRoleModel.role_id == ROLE_NAME_TO_UUID["ADMIN"],
            )
            r = await t.order._session.execute(stmt)
            if r.scalars().first() is not None:
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
            
            # Only close if all installments are PAID
            installments = order_model.installments
            all_paid = all(i.status == "PAID" for i in installments)
            
            if all_paid:
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
            # Only close if all installments are PAID
            installments = order_model.installments
            all_paid = installments and all(i.status == "PAID" for i in installments)
            if all_paid and order_model.closed_by_client:
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
            existing = (await t.order._session.execute(stmt)).scalars().first()
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
            existing = (await t.order._session.execute(stmt)).scalars().first()
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
        first_workshop = None
        first_workshop_name = None
        first_workshop_id = None
        first_workshop_rif = None
        first_workshop_address = None
        if o.items:
            first_item = o.items[0]
            first_workshop = first_item.part.workshop if first_item.part and first_item.part.workshop else None
            first_workshop_name = first_workshop.name if first_workshop else None
            first_workshop_id = str(first_item.workshop_id) if first_item.workshop_id else None
            first_workshop_rif = first_workshop.rif if first_workshop else None
            first_workshop_address = first_workshop.address if first_workshop else None

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
            workshop_rif=first_workshop_rif,
            workshop_address=first_workshop_address,
            user_first_name=o.user.first_name if o.user else "",
            user_last_name=o.user.last_name if o.user else "",
            user_ci=o.user.ci if o.user else "",
            user_email=o.user.email if o.user else "",
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
            has_pending_verification=any(
                inst.status == "PENDING_VERIFICATION" for inst in o.installments
            ),
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
