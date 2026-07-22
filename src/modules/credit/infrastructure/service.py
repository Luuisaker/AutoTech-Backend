import math
from uuid import UUID
from datetime import datetime, timezone, timedelta
from typing import Type

from fastapi import Depends
from sqlalchemy import select, func

from src.core.domain.transaction import GenericTransaction
from src.core.infrastructure.transaction import get_transaction
from src.core.application.base_response import Response
from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID, ROLE_UUID_TO_NAME
from src.config.database import get_session
from src.config.models import User as UserModel, UserRole as UserRoleModel, Installment as InstallmentModel, Order as OrderModel, OrderItem as OrderItemModel, Workshop as WorkshopModel, CreditLimitReview as CreditLimitReviewModel, LateFee as LateFeeModel, ServiceOrderInstallment as ServiceOrderInstallmentModel, ServiceOrder as ServiceOrderModel
from src.modules.credit.infrastructure.repository import (
    CreditLevelRepository,
    CreditHistoryRepository,
    CreditLimitReviewRepository,
    LateFeeRepository,
)
from src.modules.credit.application.create import (
    MyCreditLineDTO,
    CreditLineDetailDTO,
    PendingReleaseDTO,
    AdminCreditLineDTO,
    AdminCreditLineListDTO,
    CheckoutEligibilityDTO,
    CreditLevelDTO,
    LimitReviewResponse,
    AdminLimitReviewDTO,
    AdminLimitReviewListDTO,
    LateFeeDTO,
    LateFeeListDTO,
    PayLateFeeRequest,
)
from src.modules.users.infrastructure.repository import UserRepository
from src.modules.users.infrastructure.mapper import UserMapper


class CreditService:
    _mapper = UserMapper()

    def __init__(
        self, transaction: Type[GenericTransaction] = Depends(get_transaction)
    ) -> None:
        self._transaction = transaction

    async def get_my_line(self, user_id: UUID) -> Response:
        async with self._transaction(
            user=UserRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            user = await t.user.get(str(user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            level_model = await t.credit_level.get_by_level(user.credit_level)
            all_levels = await t.credit_level.list_all()
            levels_map = {lvl.level: lvl for lvl in all_levels}

            # Points to next level
            points_to_next = None
            for lvl in sorted(levels_map.keys()):
                if lvl > user.credit_level:
                    points_to_next = round(levels_map[lvl].points_required - user.credit_points, 2)
                    break

            # Pending points: sum of all pending installment amounts (potential points if paid on time)
            from src.config.models import Installment as InstModel, Order as OrdModel
            from src.config.models import ServiceOrderInstallment as SOIModel, ServiceOrder as SOModel

            # Calculate parts debt dynamically from unpaid installments
            parts_debt_stmt = (
                select(InstModel.amount)
                .join(OrdModel, InstModel.order_id == OrdModel.id)
                .where(
                    OrdModel.user_id == user_id,
                    InstModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    InstModel.deleted_at.is_(None),
                    OrdModel.deleted_at.is_(None),
                )
            )
            r = await t.user._session.execute(parts_debt_stmt)
            calculated_parts_debt = round(sum(row[0] for row in r.all()), 2)

            # Pending parts points (only PENDING + PENDING_VERIFICATION, not OVERDUE)
            parts_stmt = (
                select(InstModel.amount)
                .join(OrdModel, InstModel.order_id == OrdModel.id)
                .where(
                    OrdModel.user_id == user_id,
                    InstModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                    InstModel.deleted_at.is_(None),
                    OrdModel.deleted_at.is_(None),
                )
            )
            r = await t.user._session.execute(parts_stmt)
            pending_parts_points = sum(row[0] for row in r.all())

            # Calculate service debt dynamically
            svc_debt_stmt = (
                select(SOIModel.amount)
                .join(SOModel, SOIModel.service_order_id == SOModel.id)
                .where(
                    SOModel.user_id == user_id,
                    SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                )
            )
            r = await t.user._session.execute(svc_debt_stmt)
            calculated_service_debt = round(sum(row[0] for row in r.all()), 2)

            svc_stmt = (
                select(SOIModel.amount)
                .join(SOModel, SOIModel.service_order_id == SOModel.id)
                .where(
                    SOModel.user_id == user_id,
                    SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                )
            )
            r = await t.user._session.execute(svc_stmt)
            pending_svc_points = sum(row[0] for row in r.all())

            dto = MyCreditLineDTO(
                level=user.credit_level,
                parts_limit=user.parts_credit_limit,
                service_limit=user.service_credit_limit,
                parts_available=round(user.parts_credit_limit - calculated_parts_debt, 2),
                service_available=round(user.service_credit_limit - calculated_service_debt, 2),
                parts_debt=calculated_parts_debt,
                service_debt=calculated_service_debt,
                min_down_payment_pct=level_model.min_down_payment_pct if level_model else 0,
                credit_points=round(user.credit_points, 2),
                points_to_next_level=points_to_next,
                pending_points=round(pending_parts_points + pending_svc_points, 2),
            )
            return Response(status_code=200, success=True, content=dto)

    async def get_line_detail(self, user_id: UUID, line_type: str) -> Response:
        async with self._transaction(
            user=UserRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            user = await t.user.get(str(user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            if line_type == "parts":
                limit = user.parts_credit_limit
                # Calculate debt dynamically from unpaid installments
                from sqlalchemy import func as sql_func
                debt_stmt = (
                    select(sql_func.coalesce(sql_func.sum(InstallmentModel.amount), 0.0))
                    .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                    .where(
                        OrderModel.user_id == user_id,
                        InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                        InstallmentModel.deleted_at.is_(None),
                        OrderModel.deleted_at.is_(None),
                    )
                )
                r_debt = await t.user._session.execute(debt_stmt)
                debt = round(r_debt.scalar() or 0.0, 2)
                # Get pending installments from parts orders
                stmt = (
                    select(InstallmentModel, OrderModel, WorkshopModel)
                    .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                    .join(OrderItemModel, OrderItemModel.order_id == OrderModel.id)
                    .join(WorkshopModel, WorkshopModel.id == OrderItemModel.workshop_id)
                    .where(
                        OrderModel.user_id == user_id,
                        InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                        InstallmentModel.deleted_at.is_(None),
                        OrderModel.deleted_at.is_(None),
                    )
                    .distinct()
                )
                r = await t.user._session.execute(stmt)
                pending = []
                for inst, order, workshop in r.unique().all():
                    pending.append(PendingReleaseDTO(
                        order_id=order.id,
                        description=f"Cuota de orden — {workshop.name} #{str(order.id)[:8]}",
                        amount=inst.amount,
                        due_date=inst.due_date,
                        status=inst.status,
                    ))
            elif line_type == "service":
                limit = user.service_credit_limit
                # Calculate debt dynamically
                from src.config.models import ServiceOrderInstallment as SOIModel, ServiceOrder as SOModel
                from sqlalchemy import func as sql_func
                svc_debt_stmt = (
                    select(sql_func.coalesce(sql_func.sum(SOIModel.amount), 0.0))
                    .join(SOModel, SOIModel.service_order_id == SOModel.id)
                    .where(
                        SOModel.user_id == user_id,
                        SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    )
                )
                r_debt = await t.user._session.execute(svc_debt_stmt)
                debt = round(r_debt.scalar() or 0.0, 2)
                # Get pending service order installments
                stmt = (
                    select(SOIModel, SOModel, WorkshopModel)
                    .join(SOModel, SOIModel.service_order_id == SOModel.id)
                    .join(WorkshopModel, WorkshopModel.id == SOModel.workshop_id)
                    .where(
                        SOModel.user_id == user_id,
                        SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                    )
                )
                r = await t.user._session.execute(stmt)
                pending = []
                for inst, so, workshop in r.unique().all():
                    pending.append(PendingReleaseDTO(
                        order_id=so.id,
                        description=f"Cuota de servicio — {workshop.name} #{str(so.id)[:8]}",
                        amount=inst.amount,
                        due_date=inst.due_date,
                        status=inst.status,
                    ))
            else:
                return Response(status_code=400, success=False, message="Tipo de línea inválido")

            dto = CreditLineDetailDTO(
                line_type=line_type,
                limit=round(limit, 2),
                available=round(limit - debt, 2),
                debt=round(debt, 2),
                pending_releases=pending,
            )
            return Response(status_code=200, success=True, content=dto)

    async def user_has_open_mora(self, user_id: UUID) -> bool:
        """Check if user has any open (unpaid) late fees."""
        async with get_session() as session:
            repo = LateFeeRepository(session)
            open_fees = await repo.list_open_by_user(user_id)
            return len(open_fees) > 0

    async def check_checkout_eligibility(
        self, user_id: UUID, total_financed_parts: float, total_financed_service: float = 0.0
    ) -> Response:
        async with self._transaction(
            user=UserRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            user = await t.user.get(str(user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            # Block if user has open mora
            has_mora = await self.user_has_open_mora(user_id)
            if has_mora:
                return Response(
                    status_code=403, success=False,
                    message="Tienes moras pendientes. Paga las moras antes de continuar.",
                    content=CheckoutEligibilityDTO(
                        eligible=False,
                        parts_available=0,
                        service_available=0,
                        min_down_payment_percentage=None,
                        message="Tienes moras pendientes. Paga las moras antes de continuar.",
                    ),
                )

            # Calculate debts dynamically
            from sqlalchemy import func as sql_func
            p_debt_stmt = (
                select(sql_func.coalesce(sql_func.sum(InstallmentModel.amount), 0.0))
                .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                .where(
                    OrderModel.user_id == user_id,
                    InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    InstallmentModel.deleted_at.is_(None),
                    OrderModel.deleted_at.is_(None),
                )
            )
            r_debt = await t.user._session.execute(p_debt_stmt)
            current_parts_debt = round(r_debt.scalar() or 0.0, 2)

            from src.config.models import ServiceOrderInstallment as SOIModel, ServiceOrder as SOModel
            s_debt_stmt = (
                select(sql_func.coalesce(sql_func.sum(SOIModel.amount), 0.0))
                .join(SOModel, SOIModel.service_order_id == SOModel.id)
                .where(
                    SOModel.user_id == user_id,
                    SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                )
            )
            r_debt = await t.user._session.execute(s_debt_stmt)
            current_service_debt = round(r_debt.scalar() or 0.0, 2)

            parts_available = user.parts_credit_limit - current_parts_debt
            service_available = user.service_credit_limit - current_service_debt

            # Check parts line
            min_dp_pct = None
            message = None
            eligible = True

            if total_financed_parts > parts_available and total_financed_parts > 0:
                needed_dp_pct = ((total_financed_parts - parts_available) / total_financed_parts) * 100
                min_dp_pct = math.ceil(needed_dp_pct) + 10
                eligible = False
                message = (
                    f"Tu límite de crédito disponible es ${parts_available:.2f}. "
                    f"Necesitas un pago inicial de al menos {min_dp_pct}% "
                    f"para financiar este producto."
                )

            # Check service line (combined)
            combined_service = total_financed_service
            if combined_service > service_available and combined_service > 0:
                # Check if parts line can cover the excess
                excess = combined_service - service_available
                if excess > parts_available:
                    eligible = False
                    message = (
                        f"Tu línea de servicio disponible es ${service_available:.2f} "
                        f"y tu línea de repuestos disponible es ${parts_available:.2f}. "
                        f"Crédito insuficiente para financiar este servicio."
                    )

            dto = CheckoutEligibilityDTO(
                eligible=eligible,
                parts_available=round(parts_available, 2),
                service_available=round(service_available, 2),
                min_down_payment_percentage=min_dp_pct,
                message=message,
            )
            return Response(status_code=200, success=True, content=dto)

    async def recalculate_level(self, session, user_model) -> None:
        """Recalculate user's credit level based on points. Call within a transaction."""
        levels = await CreditLevelRepository(session).list_all()
        for lvl in levels:
            if user_model.credit_points >= lvl.points_required:
                if user_model.credit_level != lvl.level:
                    old_limit = user_model.parts_credit_limit
                    new_base = lvl.base_parts_limit
                    # Preserve admin proportional adjustment
                    old_level = await CreditLevelRepository(session).get_by_level(user_model.credit_level)
                    if old_level and old_limit > 0 and old_level.base_parts_limit > 0:
                        ratio = old_limit / old_level.base_parts_limit
                        user_model.parts_credit_limit = max(new_base, min(new_base * ratio, new_base * 3))
                    else:
                        user_model.parts_credit_limit = new_base
                    user_model.service_credit_limit = round(user_model.parts_credit_limit / 3, 2)
                    user_model.credit_level = lvl.level
                break

    async def add_credit_history(self, session, user_id: UUID, type: str, amount: float = 0.0,
                                  parts_line_used: float = 0.0, service_line_used: float = 0.0,
                                  description: str = "", reference_id: UUID | None = None) -> None:
        """Add a credit history entry. Call within a transaction."""
        repo = CreditHistoryRepository(session)
        await repo.add_entry(
            user_id=user_id, type=type, amount=amount,
            parts_line_used=parts_line_used, service_line_used=service_line_used,
            description=description, reference_id=reference_id,
        )

    async def apply_late_penalties(self, user_id: UUID) -> Response:
        """Apply per-installment late fees for overdue installments (PARTS + SERVICE)."""
        async with self._transaction(
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            user = await t.user.get(str(user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            now = datetime.now(timezone.utc)
            late_fee_repo = LateFeeRepository(t.user._session)
            total_penalty = 0.0
            moras_created = 0

            # 1. Overdue PARTS installments
            parts_stmt = (
                select(InstallmentModel)
                .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                .where(
                    OrderModel.user_id == user_id,
                    InstallmentModel.due_date < now,
                    InstallmentModel.status.notin_(["PAID"]),
                    InstallmentModel.deleted_at.is_(None),
                )
            )
            r = await t.user._session.execute(parts_stmt)
            parts_overdue = r.scalars().all()

            for inst in parts_overdue:
                # Check if open late fee already exists (dedupe)
                existing = await late_fee_repo.find_open_by_installment(inst.id, "PARTS")
                if existing:
                    continue
                days_late = (now - inst.due_date).days
                if days_late <= 0:
                    continue
                if days_late <= 4:
                    penalty = 3
                elif days_late <= 7:
                    penalty = 5
                else:
                    penalty = 10
                late_fee = LateFeeModel(
                    user_id=user_id,
                    installment_type="PARTS",
                    installment_id=inst.id,
                    amount=penalty,
                    status="PENDING",
                )
                t.user._session.add(late_fee)
                await t.user._session.flush()
                inst.status = "OVERDUE"
                t.user._session.add(inst)
                total_penalty += penalty
                moras_created += 1
                await t.credit_history.add_entry(
                    user_id=user_id, type="PENALTY", amount=-penalty,
                    description=f"Mora por cuota de partes vencida: ${penalty:.2f}",
                    reference_id=inst.id,
                )

            # 2. Overdue SERVICE installments
            svc_stmt = (
                select(ServiceOrderInstallmentModel)
                .join(ServiceOrderModel, ServiceOrderInstallmentModel.service_order_id == ServiceOrderModel.id)
                .where(
                    ServiceOrderModel.user_id == user_id,
                    ServiceOrderInstallmentModel.due_date < now,
                    ServiceOrderInstallmentModel.status.notin_(["PAID"]),
                )
            )
            r = await t.user._session.execute(svc_stmt)
            svc_overdue = r.scalars().all()

            for inst in svc_overdue:
                existing = await late_fee_repo.find_open_by_installment(inst.id, "SERVICE")
                if existing:
                    continue
                days_late = (now - inst.due_date).days
                if days_late <= 0:
                    continue
                if days_late <= 4:
                    penalty = 3
                elif days_late <= 7:
                    penalty = 5
                else:
                    penalty = 10
                late_fee = LateFeeModel(
                    user_id=user_id,
                    installment_type="SERVICE",
                    installment_id=inst.id,
                    amount=penalty,
                    status="PENDING",
                )
                t.user._session.add(late_fee)
                await t.user._session.flush()
                inst.status = "OVERDUE"
                t.user._session.add(inst)
                total_penalty += penalty
                moras_created += 1
                await t.credit_history.add_entry(
                    user_id=user_id, type="PENALTY", amount=-penalty,
                    description=f"Mora por cuota de servicio vencida: ${penalty:.2f}",
                    reference_id=inst.id,
                )

            if total_penalty > 0:
                user.credit_points = max(0, user.credit_points - total_penalty)
                await t.user.update(user)
                await self.recalculate_level(t.user._session, user)

            return Response(
                status_code=200, success=True,
                message=f"Moras creadas: {moras_created}, penalización total: -{total_penalty} puntos",
            )

    async def list_my_late_fees(self, user_id: UUID) -> Response:
        """List all late fees for the current user."""
        async with get_session() as session:
            repo = LateFeeRepository(session)
            fees = await repo.list_by_user(user_id)
            return Response(
                status_code=200, success=True,
                content=LateFeeListDTO(
                    late_fees=[
                        LateFeeDTO(
                            id=f.id,
                            installment_type=f.installment_type,
                            installment_id=f.installment_id,
                            amount=f.amount,
                            status=f.status,
                            payment_method=f.payment_method,
                            reference_number=f.reference_number,
                            rate=f.rate,
                            rate_date=f.rate_date,
                            paid_at=f.paid_at,
                            created_at=f.created_at,
                        )
                        for f in fees
                    ]
                ),
            )

    async def pay_late_fee(
        self, late_fee_id: UUID, dto: PayLateFeeRequest, user_id: UUID
    ) -> Response:
        """Client pays a late fee → status becomes PENDING_VERIFICATION."""
        async with self._transaction(
            user=UserRepository,
        ) as t:
            stmt = select(LateFeeModel).where(LateFeeModel.id == late_fee_id)
            r = await t.user._session.execute(stmt)
            fee = r.scalars().first()
            if not fee:
                return Response(status_code=404, success=False, message="Mora no encontrada")
            if fee.user_id != user_id:
                return Response(status_code=403, success=False, message="No tienes acceso a esta mora")
            if fee.status in ("PAID", "PENDING_VERIFICATION"):
                return Response(status_code=400, success=False, message="Esta mora ya fue pagada o está en verificación")

            fee.status = "PENDING_VERIFICATION"
            fee.payment_method = dto.payment_method
            fee.reference_number = dto.reference_number
            if dto.rate is not None:
                fee.rate = dto.rate
            if dto.rate_date:
                from datetime import datetime as dt
                fee.rate_date = dt.fromisoformat(dto.rate_date)
            t.user._session.add(fee)
            await t.user._session.flush()

            # Notify superadmin
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_registered_admin
                from src.config.models import User as _U, UserRole as _UR
                from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID as _RMAP
                from sqlalchemy import select as _sel
                from src.config.database import get_session as _get_session
                async with _get_session() as _s:
                    _sa = (await _s.execute(_sel(_U).join(_UR, _UR.user_id == _U.id).where(_UR.role_id == _RMAP["SUPERADMIN"]))).scalars().first()
                    _payer = (await _s.execute(_sel(_U).where(_U.id == user_id))).scalars().first()
                    if _sa and _payer:
                        await send_email(
                            _sa.email,
                            "Pago de mora registrado - AutoTech",
                            payment_registered_admin(
                                "Mora",
                                f"{_payer.first_name} {_payer.last_name}",
                                fee.amount,
                                dto.payment_method,
                                dto.reference_number,
                                lang=_sa.language_preference or "es",
                            ),
                        )
            except Exception as e:
                import logging
                logging.error(f"Error sending superadmin late fee payment email: {e}")

            return Response(
                status_code=200, success=True,
                message="Pago de mora registrado, pendiente de verificación",
                content=LateFeeDTO(
                    id=fee.id,
                    installment_type=fee.installment_type,
                    installment_id=fee.installment_id,
                    amount=fee.amount,
                    status=fee.status,
                    payment_method=fee.payment_method,
                    reference_number=fee.reference_number,
                    rate=fee.rate,
                    rate_date=fee.rate_date,
                    paid_at=fee.paid_at,
                    created_at=fee.created_at,
                ),
            )

    async def mark_late_fee_paid(
        self, late_fee_id: UUID, user_id: UUID
    ) -> Response:
        """Workshop owner or admin marks a late fee as PAID."""
        async with self._transaction(
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            stmt = select(LateFeeModel).where(LateFeeModel.id == late_fee_id)
            r = await t.user._session.execute(stmt)
            fee = r.scalars().first()
            if not fee:
                return Response(status_code=404, success=False, message="Mora no encontrada")

            # Check admin or workshop_owner
            admin_stmt = select(UserRoleModel).where(
                UserRoleModel.user_id == user_id,
                UserRoleModel.role_id.in_([ROLE_NAME_TO_UUID["ADMIN"], ROLE_NAME_TO_UUID["WORKSHOP_OWNER"]]),
            )
            admin_r = await t.user._session.execute(admin_stmt)
            if not admin_r.scalars().first():
                return Response(status_code=403, success=False, message="No tienes permisos para verificar moras")

            if fee.status == "PAID":
                return Response(status_code=400, success=False, message="Esta mora ya fue pagada")

            fee.status = "PAID"
            fee.paid_at = datetime.now(timezone.utc)
            t.user._session.add(fee)
            await t.user._session.flush()

            return Response(
                status_code=200, success=True,
                message="Mora marcada como pagada",
                content=LateFeeDTO(
                    id=fee.id,
                    installment_type=fee.installment_type,
                    installment_id=fee.installment_id,
                    amount=fee.amount,
                    status=fee.status,
                    payment_method=fee.payment_method,
                    reference_number=fee.reference_number,
                    rate=fee.rate,
                    rate_date=fee.rate_date,
                    paid_at=fee.paid_at,
                    created_at=fee.created_at,
                ),
            )

    async def admin_list_lines(self) -> Response:
        """Admin: list all users' credit lines with stats."""
        async with get_session() as session:
            stmt = (
                select(UserModel)
                .join(UserRoleModel, UserRoleModel.user_id == UserModel.id)
                .where(UserModel.deleted_at.is_(None))
                .where(UserRoleModel.role_id.in_([ROLE_NAME_TO_UUID["CLIENT"], ROLE_NAME_TO_UUID["WORKSHOP_OWNER"]]))
                .order_by(UserModel.credit_level.desc())
            )
            r = await session.execute(stmt)
            users = r.unique().scalars().all()

            # Get credit levels for reference
            levels = await CreditLevelRepository(session).list_all()
            levels_map = {lvl.level: lvl for lvl in levels}

            # Calculate debts dynamically for all users at once
            from src.config.models import Installment as InstModel, Order as OrdModel
            from src.config.models import ServiceOrderInstallment as SOIModel, ServiceOrder as SOModel
            from sqlalchemy import func

            parts_debt_stmt = (
                select(OrdModel.user_id, func.coalesce(func.sum(InstModel.amount), 0.0))
                .join(InstModel, InstModel.order_id == OrdModel.id)
                .where(
                    InstModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    InstModel.deleted_at.is_(None),
                    OrdModel.deleted_at.is_(None),
                )
                .group_by(OrdModel.user_id)
            )
            r = await session.execute(parts_debt_stmt)
            parts_debt_map = {row[0]: round(row[1], 2) for row in r.all()}

            svc_debt_stmt = (
                select(SOModel.user_id, func.coalesce(func.sum(SOIModel.amount), 0.0))
                .join(SOIModel, SOIModel.service_order_id == SOModel.id)
                .where(
                    SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                )
                .group_by(SOModel.user_id)
            )
            r = await session.execute(svc_debt_stmt)
            svc_debt_map = {row[0]: round(row[1], 2) for row in r.all()}

            dtos = []
            for u in users:
                # Calculate next level points
                points_to_next = None
                for lvl in sorted(levels_map.keys()):
                    if lvl > u.credit_level:
                        points_to_next = round(levels_map[lvl].points_required - u.credit_points, 2)
                        break

                # Calculate manual adjustment
                base = levels_map.get(u.credit_level)
                manual_adj = None
                if base and u.parts_credit_limit > base.base_parts_limit:
                    manual_adj = round(u.parts_credit_limit - base.base_parts_limit, 2)

                p_debt = parts_debt_map.get(u.id, 0.0)
                s_debt = svc_debt_map.get(u.id, 0.0)

                dto = AdminCreditLineDTO(
                    user_id=u.id,
                    user_name=f"{u.first_name} {u.last_name}",
                    user_email=u.email,
                    user_roles=[ROLE_UUID_TO_NAME.get(str(ur.role_id), "CLIENT") for ur in u.roles] if u.roles else [],
                    level=u.credit_level,
                    credit_points=round(u.credit_points, 2),
                    points_to_next_level=points_to_next,
                    parts_limit=round(u.parts_credit_limit, 2),
                    service_limit=round(u.service_credit_limit, 2),
                    parts_available=round(u.parts_credit_limit - p_debt, 2),
                    service_available=round(u.service_credit_limit - s_debt, 2),
                    parts_debt=p_debt,
                    service_debt=s_debt,
                    manual_adjustment=manual_adj,
                    client_average_rating=round(u.client_average_rating, 1) if u.client_rating_count > 0 else 0.0,
                    client_rating_count=u.client_rating_count,
                )
                dtos.append(dto)

            return Response(status_code=200, success=True, content=AdminCreditLineListDTO(lines=dtos))

    async def admin_get_line(self, user_id: UUID) -> Response:
        """Admin: get a single user's credit line with full stats."""
        async with get_session() as session:
            user = await session.get(UserModel, user_id)
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            levels = await CreditLevelRepository(session).list_all()
            levels_map = {lvl.level: lvl for lvl in levels}

            points_to_next = None
            for lvl in sorted(levels_map.keys()):
                if lvl > user.credit_level:
                    points_to_next = round(levels_map[lvl].points_required - user.credit_points, 2)
                    break

            base = levels_map.get(user.credit_level)
            manual_adj = None
            if base and user.parts_credit_limit > base.base_parts_limit:
                manual_adj = round(user.parts_credit_limit - base.base_parts_limit, 2)

            # Gather stats
            from src.config.models import (
                Order as OrderModel, Installment as InstallmentModel,
                ServiceOrder as SOModel, ServiceOrderInstallment as SOIModel,
            )

            # Parts orders stats
            orders_stmt = (
                select(func.count(OrderModel.id))
                .where(OrderModel.user_id == user_id, OrderModel.deleted_at.is_(None))
            )
            parts_orders_count = (await session.execute(orders_stmt)).scalar() or 0

            # Installments on time / late
            inst_stmt = (
                select(InstallmentModel)
                .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                .where(OrderModel.user_id == user_id, InstallmentModel.deleted_at.is_(None))
            )
            insts = (await session.execute(inst_stmt)).scalars().all()
            on_time = sum(1 for i in insts if i.status == "PAID" and (i.paid_at is None or i.paid_at <= i.due_date))
            late = sum(1 for i in insts if i.status == "PAID" and i.paid_at is not None and i.paid_at > i.due_date)

            # Service orders stats
            so_stmt = select(func.count(SOModel.id)).where(SOModel.user_id == user_id)
            service_orders_count = (await session.execute(so_stmt)).scalar() or 0
            service_cash = sum(1 for so in (await session.execute(select(SOModel).where(SOModel.user_id == user_id))).scalars().all() if so.is_financed == 0)
            service_financed = service_orders_count - service_cash

            # Total spent
            total_spent_stmt = (
                select(func.coalesce(func.sum(InstallmentModel.amount), 0.0))
                .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                .where(OrderModel.user_id == user_id, InstallmentModel.status == "PAID")
            )
            total_spent = (await session.execute(total_spent_stmt)).scalar() or 0.0

            # Calculate debts dynamically
            p_debt_stmt = (
                select(func.coalesce(func.sum(InstallmentModel.amount), 0.0))
                .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                .where(
                    OrderModel.user_id == user_id,
                    InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    InstallmentModel.deleted_at.is_(None),
                    OrderModel.deleted_at.is_(None),
                )
            )
            p_debt = round((await session.execute(p_debt_stmt)).scalar() or 0.0, 2)

            s_debt_stmt = (
                select(func.coalesce(func.sum(SOIModel.amount), 0.0))
                .join(SOModel, SOIModel.service_order_id == SOModel.id)
                .where(
                    SOModel.user_id == user_id,
                    SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                )
            )
            s_debt = round((await session.execute(s_debt_stmt)).scalar() or 0.0, 2)

            dto = AdminCreditLineDTO(
                user_id=user.id,
                user_name=f"{user.first_name} {user.last_name}",
                user_email=user.email,
                level=user.credit_level,
                credit_points=round(user.credit_points, 2),
                points_to_next_level=points_to_next,
                parts_limit=round(user.parts_credit_limit, 2),
                service_limit=round(user.service_credit_limit, 2),
                parts_available=round(user.parts_credit_limit - p_debt, 2),
                service_available=round(user.service_credit_limit - s_debt, 2),
                parts_debt=p_debt,
                service_debt=s_debt,
                total_spent=round(total_spent, 2),
                parts_orders_count=parts_orders_count,
                parts_installments_on_time=on_time,
                parts_installments_late=late,
                service_orders_count=service_orders_count,
                service_orders_cash=service_cash,
                service_orders_financed=service_financed,
                manual_adjustment=manual_adj,
                client_average_rating=round(user.client_average_rating, 1) if user.client_rating_count > 0 else 0.0,
                client_rating_count=user.client_rating_count,
            )
            return Response(status_code=200, success=True, content=dto)

    async def admin_update_line(self, user_id: UUID, parts_limit: float | None, service_limit: float | None) -> Response:
        """Admin: manually adjust a user's credit limits."""
        async with self._transaction(
            user=UserRepository,
            credit_level=CreditLevelRepository,
            credit_history=CreditHistoryRepository,
        ) as t:
            user = await t.user.get(str(user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            levels = await t.credit_level.list_all()
            levels_map = {lvl.level: lvl for lvl in levels}
            base = levels_map.get(user.credit_level)

            if parts_limit is not None:
                if base:
                    if parts_limit < base.base_parts_limit:
                        return Response(
                            status_code=400, success=False,
                            message=f"El límite no puede ser menor al base del nivel {user.credit_level}: ${base.base_parts_limit:.2f}",
                        )
                    if parts_limit > base.base_parts_limit * 3:
                        return Response(
                            status_code=400, success=False,
                            message=f"El límite no puede exceder 3x el base del nivel {user.credit_level}: ${base.base_parts_limit * 3:.2f}",
                        )
                user.parts_credit_limit = parts_limit
                user.service_credit_limit = round(parts_limit / 3, 2)

            if service_limit is not None:
                user.service_credit_limit = service_limit

            await t.user.update(user)

            await t.credit_history.add_entry(
                user_id=user_id, type="ADMIN_ADJUST",
                amount=0.0,
                description=f"Ajuste manual: parts=${user.parts_credit_limit}, service=${user.service_credit_limit}",
            )

            # Calculate debts dynamically for response
            from sqlalchemy import func as sql_func
            p_debt_stmt = (
                select(sql_func.coalesce(sql_func.sum(InstallmentModel.amount), 0.0))
                .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                .where(
                    OrderModel.user_id == user_id,
                    InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    InstallmentModel.deleted_at.is_(None),
                    OrderModel.deleted_at.is_(None),
                )
            )
            r_debt = await t.user._session.execute(p_debt_stmt)
            p_debt = round(r_debt.scalar() or 0.0, 2)

            from src.config.models import ServiceOrderInstallment as SOIModel, ServiceOrder as SOModel
            s_debt_stmt = (
                select(sql_func.coalesce(sql_func.sum(SOIModel.amount), 0.0))
                .join(SOModel, SOIModel.service_order_id == SOModel.id)
                .where(
                    SOModel.user_id == user_id,
                    SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                )
            )
            r_debt = await t.user._session.execute(s_debt_stmt)
            s_debt = round(r_debt.scalar() or 0.0, 2)

            return Response(
                status_code=200, success=True,
                message="Línea de crédito actualizada",
                content=MyCreditLineDTO(
                    level=user.credit_level,
                    parts_limit=round(user.parts_credit_limit, 2),
                    service_limit=round(user.service_credit_limit, 2),
                    parts_available=round(user.parts_credit_limit - p_debt, 2),
                    service_available=round(user.service_credit_limit - s_debt, 2),
                    parts_debt=p_debt,
                    service_debt=s_debt,
                ),
            )


    async def request_limit_review(self, user_id: UUID) -> Response:
        async with self._transaction(
            user=UserRepository,
            credit_level=CreditLevelRepository,
            credit_limit_review=CreditLimitReviewRepository,
        ) as t:
            user = await t.user.get(str(user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")
            if user.credit_level < 4:
                return Response(
                    status_code=403, success=False,
                    message="Solo los usuarios nivel 4 pueden solicitar revisión de límite",
                )

            # Check for pending request
            last = await t.credit_limit_review.get_last_by_user(str(user_id))
            if last and last.status == "PENDING":
                return Response(
                    status_code=400, success=False,
                    message="Ya tienes una solicitud pendiente",
                )
            if last and last.status == "REJECTED":
                three_months_ago = datetime.now(timezone.utc) - timedelta(days=90)
                if last.created_at and last.created_at > three_months_ago:
                    next_date = last.created_at + timedelta(days=90)
                    return Response(
                        status_code=400, success=False,
                        message=(
                            f"Debes esperar 3 meses entre solicitudes. "
                            f"Próxima fecha disponible: {next_date.strftime('%d/%m/%Y')}"
                        ),
                    )

            review = CreditLimitReviewModel(user_id=user.id, status="PENDING")
            await t.credit_limit_review.add(review)

            return Response(
                status_code=200, success=True,
                message="Solicitud de revisión enviada",
            )

    async def get_my_limit_requests(self, user_id: UUID) -> Response:
        async with self._transaction(
            credit_limit_review=CreditLimitReviewRepository,
            user=UserRepository,
        ) as t:
            user = await t.user.get(str(user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            requests = await t.credit_limit_review.list_by_user(str(user_id))
            return Response(
                status_code=200, success=True,
                content=[LimitReviewResponse(
                    id=r.id,
                    user_id=r.user_id,
                    status=r.status,
                    created_at=r.created_at,
                    reviewed_at=r.reviewed_at,
                    reviewed_by=r.reviewed_by,
                    reviewer_name=None,
                ) for r in requests],
            )

    async def admin_list_limit_requests(self) -> Response:
        async with self._transaction(
            credit_limit_review=CreditLimitReviewRepository,
            user=UserRepository,
        ) as t:
            requests = await t.credit_limit_review.list_pending()
            result = []
            for r in requests:
                u = await t.user.get(str(r.user_id))
                result.append(AdminLimitReviewDTO(
                    id=r.id,
                    user_id=r.user_id,
                    user_name=f"{u.first_name} {u.last_name}" if u else "N/A",
                    user_email=u.email if u else "N/A",
                    current_parts_limit=u.parts_credit_limit if u else 0,
                    status=r.status,
                    created_at=r.created_at,
                    reviewed_at=r.reviewed_at,
                    reviewer_name=None,
                ))
            return Response(
                status_code=200, success=True,
                content=AdminLimitReviewListDTO(requests=result),
            )

    async def admin_review_limit_request(
        self, request_id: UUID, admin_id: UUID, dto
    ) -> Response:
        async with self._transaction(
            credit_limit_review=CreditLimitReviewRepository,
            user=UserRepository,
            credit_history=CreditHistoryRepository,
            credit_level=CreditLevelRepository,
        ) as t:
            review = await t.credit_limit_review.get(str(request_id))
            if not review:
                return Response(status_code=404, success=False, message="Solicitud no encontrada")
            if review.status != "PENDING":
                return Response(status_code=400, success=False, message="La solicitud ya fue revisada")

            user = await t.user.get(str(review.user_id))
            if not user:
                return Response(status_code=404, success=False, message="Usuario no encontrado")

            if dto.action == "APPROVED":
                if not dto.new_parts_limit or dto.new_parts_limit <= 0:
                    return Response(
                        status_code=400, success=False,
                        message="Debes especificar un nuevo límite de repuestos válido",
                    )
                old_parts = user.parts_credit_limit
                user.parts_credit_limit = dto.new_parts_limit
                user.service_credit_limit = round(dto.new_parts_limit / 3, 2)
                await t.user.update(user)

                await t.credit_history.add_entry(
                    user_id=review.user_id,
                    type="ADMIN_ADJUST",
                    amount=0.0,
                    description=f"Revisión de límite aprobada: ${old_parts:.2f} → ${dto.new_parts_limit:.2f}",
                )

                review.status = "APPROVED"
                review.reviewed_by = admin_id
                review.reviewed_at = datetime.now(timezone.utc)
                await t.credit_limit_review.update(review)

                return Response(
                    status_code=200, success=True,
                    message=f"Solicitud aprobada. Nuevo límite: ${dto.new_parts_limit:.2f}",
                )
            else:
                review.status = "REJECTED"
                review.reviewed_by = admin_id
                review.reviewed_at = datetime.now(timezone.utc)
                await t.credit_limit_review.update(review)

                return Response(
                    status_code=200, success=True,
                    message="Solicitud rechazada",
                )


def get_credit_service(
    transaction: Type[GenericTransaction] = Depends(get_transaction),
) -> CreditService:
    return CreditService(transaction=transaction)
