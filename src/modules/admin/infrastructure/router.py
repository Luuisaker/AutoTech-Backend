from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import Depends, APIRouter, Response, Query, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.orm import selectinload
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.config.database import get_session
from src.config.models import (
    User as UserModel,
    Workshop as WorkshopModel,
    Part as PartModel,
    Vehicle as VehicleModel,
    UserRole as UserRoleModel,
    WorkshopService as WorkshopServiceModel,
    Order as OrderModel,
    OrderItem as OrderItemModel,
    Installment as InstallmentModel,
    ServiceOrder as ServiceOrderModel,
    ServiceOrderInstallment as ServiceOrderInstallmentModel,
    ServiceOrderPayment as ServiceOrderPaymentModel,
    WorkshopCommission as WorkshopCommissionModel,
    Review as ReviewModel,
    OrderReview as OrderReviewModel,
    Transaction as TransactionModel,
    CreditHistory as CreditHistoryModel,
    LateFee as LateFeeModel,
    VehicleHistoryLog as VehicleHistoryLogModel,
    AssistanceRequest as AssistanceRequestModel,
    Cart as CartModel,
    CartItem as CartItemModel,
    TrustedDevice as TrustedDeviceModel,
    UserPaymentAccount as UserPaymentAccountModel,
    CreditLimitReview as CreditLimitReviewModel,
    PartPurchase as PartPurchaseModel,
    PartPayment as PartPaymentModel,
    SupportMessage as SupportMessageModel,
)
from src.modules.users.infrastructure.auth import CurrentUser, ROLE_NAME_TO_UUID, ROLE_UUID_TO_NAME, get_current_user
from src.modules.users.infrastructure.permissions import require_admin, require_superadmin
from src.modules.users.infrastructure.repository import UserRepository
from src.modules.users.infrastructure.mapper import UserMapper
from src.modules.users.infrastructure.user_dto_helper import user_to_dto
from src.modules.users.application.create import UserDTO
from src.modules.vehicles.application.create import VehicleDTO, VehicleListDTO
from src.modules.workshops.application.create import WorkshopDTO
from src.modules.parts.application.create import PartDTO
from src.modules.workshops.infrastructure.repository import WorkshopRepository
from pydantic import BaseModel


class AdminPartUpdateRequest(BaseModel):
    name: str | None = None
    price: float | None = None
    stock: int | None = None
    is_active: int | None = None


class AdminVehicleUpdateRequest(BaseModel):
    brand: str | None = None
    model: str | None = None
    year: int | None = None
    license_plate: str | None = None
    vehicle_type: str | None = None
    is_active: int | None = None


class AdminWorkshopDTO(BaseModel):
    id: str
    owner_id: str
    owner_name: str
    name: str
    rif: str
    address: str
    is_certified: int
    is_suspended: int
    average_rating: float
    verification_document_url: str | None
    photo_url: str | None
    created_at: str

    model_config = {"from_attributes": True}


class AdminWorkshopListDTO(BaseModel):
    workshops: list[AdminWorkshopDTO]


class AdminStatsDTO(BaseModel):
    total_users: int
    total_workshops: int
    total_certified_workshops: int
    total_parts: int
    total_vehicles: int
    total_sales: int
    total_revenue: float
    total_financed: float
    total_credit_limit: float
    total_credit_available: float
    total_financing: float


class AdminWorkshopEarningsDTO(BaseModel):
    workshop_id: str
    workshop_name: str
    sales_count: int
    total_revenue: float
    paid_amount: float
    pending_amount: float


class AdminOwnerEarningsDTO(BaseModel):
    owner_id: str
    owner_name: str
    total_sales: int
    total_revenue: float
    total_paid: float
    total_pending: float
    workshops: list[AdminWorkshopEarningsDTO]


class AdminEarningsListDTO(BaseModel):
    owners: list[AdminOwnerEarningsDTO]


class AdminPartDTO(BaseModel):
    id: UUID
    workshop_id: UUID
    workshop_name: str
    name: str
    description: str | None
    price: float
    stock: int
    condition: str
    category: str | None
    allows_installments: int
    installment_min_percentage: float
    photo_url: str | None
    is_active: int
    created_at: datetime

    model_config = {"from_attributes": True}


class AdminPartListDTO(BaseModel):
    parts: list[AdminPartDTO]


class AdminUpdateUserRequest(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    phone: str | None = None
    roles: list[str] | None = None
    is_suspended: int | None = None
    language_preference: str | None = None


class AdminUpdateWorkshopRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    rif: str | None = None
    is_certified: int | None = None
    is_suspended: int | None = None


async def _count_open_orders(session, kind: str, id: UUID) -> int:
    """Count open orders (parts orders + service orders) tied to a user, workshop or vehicle."""
    if kind == "users":
        # Parts orders (buyer)
        c1 = (
            await session.execute(
                select(func.count(OrderModel.id)).where(
                    OrderModel.user_id == id,
                    OrderModel.deleted_at.is_(None),
                    OrderModel.status.not_in(["CLOSED", "CANCELLED", "REFUNDED"]),
                )
            )
        ).scalar() or 0
        # Parts orders (workshop owner)
        c2 = (
            await session.execute(
                select(func.count(OrderModel.id))
                .join(OrderItemModel, OrderItemModel.order_id == OrderModel.id)
                .join(WorkshopModel, WorkshopModel.id == OrderItemModel.workshop_id)
                .where(
                    WorkshopModel.owner_id == id,
                    OrderModel.deleted_at.is_(None),
                    OrderModel.status.not_in(["CLOSED", "CANCELLED", "REFUNDED"]),
                )
            )
        ).scalar() or 0
        # Service orders (buyer)
        c3 = (
            await session.execute(
                select(func.count(ServiceOrderModel.id)).where(
                    ServiceOrderModel.user_id == id,
                    ServiceOrderModel.status.not_in(["CLOSED", "CANCELLED"]),
                )
            )
        ).scalar() or 0
        return int(c1 + c2 + c3)
    if kind == "workshops":
        # Parts orders
        c1 = (
            await session.execute(
                select(func.count(OrderModel.id))
                .join(OrderItemModel, OrderItemModel.order_id == OrderModel.id)
                .where(
                    OrderItemModel.workshop_id == id,
                    OrderModel.deleted_at.is_(None),
                    OrderModel.status.not_in(["CLOSED", "CANCELLED", "REFUNDED"]),
                )
            )
        ).scalar() or 0
        # Service orders
        c2 = (
            await session.execute(
                select(func.count(ServiceOrderModel.id)).where(
                    ServiceOrderModel.workshop_id == id,
                    ServiceOrderModel.status.not_in(["CLOSED", "CANCELLED"]),
                )
            )
        ).scalar() or 0
        return int(c1 + c2)
    if kind == "vehicles":
        # Service orders
        c1 = (
            await session.execute(
                select(func.count(ServiceOrderModel.id)).where(
                    ServiceOrderModel.vehicle_id == id,
                    ServiceOrderModel.status.not_in(["CLOSED", "CANCELLED"]),
                )
            )
        ).scalar() or 0
        # Parts orders
        c2 = (
            await session.execute(
                select(func.count(OrderModel.id)).where(
                    OrderModel.vehicle_id == id,
                    OrderModel.deleted_at.is_(None),
                    OrderModel.status.not_in(["CLOSED", "CANCELLED", "REFUNDED"]),
                )
            )
        ).scalar() or 0
        return int(c1 + c2)
    return 0


class AdminRouter(BaseRouter):
    __prefix__ = "/admin"
    __tag__ = "Admin"

    def __init__(self) -> None:
        super().__init__(APIRouter(prefix=self.__prefix__, tags=[self.__tag__]))

    def _register_routes(self) -> None:
        @self._router.get("/stats", response_model=CoreResponse[AdminStatsDTO])
        async def get_stats(
            _: CurrentUser = Depends(require_admin),
        ):
            from src.config.models import ServiceOrderInstallment as AdminSOI, ServiceOrder as AdminSO
            async with get_session() as session:
                not_admin_subq = select(UserRoleModel.user_id).where(
                    UserRoleModel.role_id == ROLE_NAME_TO_UUID["ADMIN"]
                )
                user_count = (
                    await session.execute(
                        select(func.count(UserModel.id))
                        .where(UserModel.deleted_at.is_(None))
                        .where(UserModel.id.notin_(not_admin_subq))
                    )
                ).scalar() or 0
                workshop_count = (
                    await session.execute(select(func.count(WorkshopModel.id)))
                ).scalar() or 0
                certified_count = (
                    await session.execute(
                        select(func.count(WorkshopModel.id)).where(
                            WorkshopModel.is_certified == 1
                        )
                    )
                ).scalar() or 0
                part_count = (
                    await session.execute(select(func.count(PartModel.id)))
                ).scalar() or 0
                vehicle_count = (
                    await session.execute(select(func.count(VehicleModel.id)))
                ).scalar() or 0

                total_sales = (
                    await session.execute(
                        select(func.count(OrderModel.id)).where(
                            OrderModel.deleted_at.is_(None)
                        )
                    )
                ).scalar() or 0

                # Monthly revenue: sum of PAID installments in last 30 days
                thirty_days_ago = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=30)
                parts_revenue_result = await session.execute(
                    select(func.coalesce(func.sum(InstallmentModel.amount), 0)).where(
                        InstallmentModel.status == "PAID",
                        InstallmentModel.deleted_at.is_(None),
                        InstallmentModel.paid_at >= thirty_days_ago,
                    )
                )
                monthly_parts_revenue = float(parts_revenue_result.scalar() or 0.0)

                service_revenue_result = await session.execute(
                    select(func.coalesce(func.sum(AdminSOI.amount), 0)).where(
                        AdminSOI.status == "PAID",
                        AdminSOI.paid_at >= thirty_days_ago,
                    )
                )
                monthly_service_revenue = float(service_revenue_result.scalar() or 0.0)

                # Include PAID commissions and late fees in monthly revenue
                commission_revenue_result = await session.execute(
                    select(func.coalesce(func.sum(WorkshopCommissionModel.commission_amount), 0)).where(
                        WorkshopCommissionModel.status == "PAID",
                        WorkshopCommissionModel.paid_at >= thirty_days_ago,
                    )
                )
                monthly_commission_revenue = float(commission_revenue_result.scalar() or 0.0)

                from src.config.models import LateFee as AdminLF
                late_fee_revenue_result = await session.execute(
                    select(func.coalesce(func.sum(AdminLF.amount), 0)).where(
                        AdminLF.status == "PAID",
                        AdminLF.paid_at >= thirty_days_ago,
                    )
                )
                monthly_late_fee_revenue = float(late_fee_revenue_result.scalar() or 0.0)

                monthly_revenue = monthly_parts_revenue + monthly_service_revenue + monthly_commission_revenue + monthly_late_fee_revenue

                # Total financed (all-time: sum of ALL installments ever created, paid or not)
                financed_result = await session.execute(
                    select(func.coalesce(func.sum(InstallmentModel.amount), 0)).where(
                        InstallmentModel.deleted_at.is_(None),
                    )
                )
                total_financed = float(financed_result.scalar() or 0.0)

            # Credit line aggregates (non-admin, non-deleted users)
            # Calculate total financing dynamically from unpaid installments
            total_parts_financing_stmt = (
                select(func.coalesce(func.sum(InstallmentModel.amount), 0.0))
                .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                .where(
                    InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    InstallmentModel.deleted_at.is_(None),
                    OrderModel.deleted_at.is_(None),
                )
            )
            total_parts_financing = float((await session.execute(total_parts_financing_stmt)).scalar() or 0.0)

            total_service_financing_stmt = (
                select(func.coalesce(func.sum(AdminSOI.amount), 0.0))
                .join(AdminSO, AdminSOI.service_order_id == AdminSO.id)
                .where(
                    AdminSOI.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                )
            )
            total_service_financing = float((await session.execute(total_service_financing_stmt)).scalar() or 0.0)

            total_credit_limit_result = await session.execute(
                select(func.coalesce(func.sum(UserModel.parts_credit_limit), 0))
                .where(UserModel.deleted_at.is_(None))
                .where(UserModel.id.notin_(not_admin_subq))
            )
            total_credit_limit = float(total_credit_limit_result.scalar() or 0.0)
            total_financing = total_parts_financing + total_service_financing
            total_credit_available = total_credit_limit - total_financing

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminStatsDTO(
                    total_users=user_count,
                    total_workshops=workshop_count,
                    total_certified_workshops=certified_count,
                    total_parts=part_count,
                    total_vehicles=vehicle_count,
                    total_sales=total_sales,
                    total_revenue=monthly_revenue,
                    total_financed=total_financed,
                    total_credit_limit=total_credit_limit,
                    total_credit_available=total_credit_available,
                    total_financing=total_financing,
                ),
            )

        # --- Open Orders Check (for delete protection) ---
        @self._router.get("/users/{id}/open-orders")
        async def user_open_orders(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            import json
            from fastapi import Response as FastResponse
            async with get_session() as session:
                count = await _count_open_orders(session, "users", id)
            return FastResponse(
                content=json.dumps({"success": True, "status_code": 200, "content": {"open_orders": count}}),
                media_type="application/json",
                status_code=200,
            )

        @self._router.get("/workshops/{id}/open-orders")
        async def workshop_open_orders(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            import json
            from fastapi import Response as FastResponse
            async with get_session() as session:
                count = await _count_open_orders(session, "workshops", id)
            return FastResponse(
                content=json.dumps({"success": True, "status_code": 200, "content": {"open_orders": count}}),
                media_type="application/json",
                status_code=200,
            )

        @self._router.get("/vehicles/{id}/open-orders")
        async def vehicle_open_orders(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            import json
            from fastapi import Response as FastResponse
            async with get_session() as session:
                count = await _count_open_orders(session, "vehicles", id)
            return FastResponse(
                content=json.dumps({"success": True, "status_code": 200, "content": {"open_orders": count}}),
                media_type="application/json",
                status_code=200,
            )

        # --- Earnings ---

        def _earnings_start_date(period: str) -> datetime:
            now = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            if period == "month":
                return now - timedelta(days=30)
            elif period == "3months":
                return now - timedelta(days=90)
            elif period == "6months":
                return now - timedelta(days=180)
            elif period == "year":
                return now - timedelta(days=365)
            return now - timedelta(days=30)

        @self._router.get("/earnings", response_model=CoreResponse[AdminEarningsListDTO])
        async def list_earnings(
            period: str = Query(default="month", pattern=r"^(month|3months|6months|year)$"),
            _: CurrentUser = Depends(require_admin),
        ):
            start_date = _earnings_start_date(period)

            async with get_session() as session:
                # ── Subquery: installment stats per order ──
                inst_subq = (
                    select(
                        InstallmentModel.order_id.label("oid"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (InstallmentModel.status == "PAID", InstallmentModel.amount),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("paid"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]), InstallmentModel.amount),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("pending"),
                    )
                    .where(InstallmentModel.deleted_at.is_(None))
                    .group_by(InstallmentModel.order_id)
                    .subquery()
                )

                # ── Subquery: order revenue per (order, workshop) ──
                # Each order may have items from multiple workshops; allocate total_amount
                # proportionally by workshop item subtotal
                item_subq = (
                    select(
                        OrderItemModel.order_id.label("oid"),
                        OrderItemModel.workshop_id.label("wid"),
                        func.sum(OrderItemModel.unit_price * OrderItemModel.quantity).label("ws_subtotal"),
                    )
                    .group_by(OrderItemModel.order_id, OrderItemModel.workshop_id)
                    .subquery()
                )

                # ── Orders (parts) — proportional allocation per workshop ──
                order_stmt = (
                    select(
                        WorkshopModel.owner_id,
                        UserModel.first_name,
                        UserModel.last_name,
                        WorkshopModel.id,
                        WorkshopModel.name,
                        func.count(OrderModel.id.distinct()).label("order_count"),
                        func.coalesce(func.sum(item_subq.c.ws_subtotal), 0).label("order_revenue"),
                        func.coalesce(
                            func.sum(
                                inst_subq.c.paid * item_subq.c.ws_subtotal / func.nullif(OrderModel.total_amount, 0)
                            ),
                            0,
                        ).label("order_paid"),
                        func.coalesce(
                            func.sum(
                                inst_subq.c.pending * item_subq.c.ws_subtotal / func.nullif(OrderModel.total_amount, 0)
                            ),
                            0,
                        ).label("order_pending"),
                    )
                    .select_from(OrderModel)
                    .join(item_subq, item_subq.c.oid == OrderModel.id)
                    .join(WorkshopModel, WorkshopModel.id == item_subq.c.wid)
                    .join(UserModel, UserModel.id == WorkshopModel.owner_id)
                    .outerjoin(inst_subq, inst_subq.c.oid == OrderModel.id)
                    .where(
                        OrderModel.deleted_at.is_(None),
                        OrderModel.created_at >= start_date,
                    )
                    .group_by(
                        WorkshopModel.owner_id,
                        UserModel.first_name,
                        UserModel.last_name,
                        WorkshopModel.id,
                        WorkshopModel.name,
                    )
                )
                order_rows = (await session.execute(order_stmt)).all()

                # ── Service Orders ──
                # Subquery: service installment stats per service order
                svc_inst_subq = (
                    select(
                        ServiceOrderInstallmentModel.service_order_id.label("soid"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (ServiceOrderInstallmentModel.status == "PAID", ServiceOrderInstallmentModel.amount),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("paid"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (ServiceOrderInstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]), ServiceOrderInstallmentModel.amount),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("pending"),
                    )
                    .group_by(ServiceOrderInstallmentModel.service_order_id)
                    .subquery()
                )

                svc_stmt = (
                    select(
                        WorkshopModel.owner_id,
                        UserModel.first_name,
                        UserModel.last_name,
                        WorkshopModel.id,
                        WorkshopModel.name,
                        func.count(ServiceOrderModel.id).label("svc_count"),
                        func.coalesce(
                            func.sum(
                                func.coalesce(ServiceOrderModel.final_price, ServiceOrderModel.base_price)
                            ),
                            0,
                        ).label("svc_revenue"),
                        func.coalesce(
                            func.sum(
                                func.coalesce(svc_inst_subq.c.paid, 0)
                            ),
                            0,
                        ).label("svc_paid"),
                        func.coalesce(
                            func.sum(
                                func.coalesce(svc_inst_subq.c.pending, 0)
                            ),
                            0,
                        ).label("svc_pending"),
                    )
                    .select_from(ServiceOrderModel)
                    .join(WorkshopModel, WorkshopModel.id == ServiceOrderModel.workshop_id)
                    .join(UserModel, UserModel.id == WorkshopModel.owner_id)
                    .outerjoin(svc_inst_subq, svc_inst_subq.c.soid == ServiceOrderModel.id)
                    .where(ServiceOrderModel.created_at >= start_date)
                    .group_by(
                        WorkshopModel.owner_id,
                        UserModel.first_name,
                        UserModel.last_name,
                        WorkshopModel.id,
                        WorkshopModel.name,
                    )
                )
                svc_rows = (await session.execute(svc_stmt)).all()

            # Merge by (owner_id, workshop_id)
            merged: dict[tuple[str, str], dict] = {}

            def ensure_owner(owner_id: str, owner_name: str):
                for (_oid, _wid), data in merged.items():
                    if _oid == owner_id:
                        return data
                return None

            def get_ws_key(owner_id: str, ws_id: str):
                return (str(owner_id), str(ws_id))

            for row in order_rows:
                owner_id = str(row.owner_id)
                ws_id = str(row.id)
                key = get_ws_key(owner_id, ws_id)
                merged[key] = {
                    "owner_id": owner_id,
                    "owner_name": f"{row.first_name} {row.last_name}".strip(),
                    "ws_id": ws_id,
                    "ws_name": row.name,
                    "sales_count": row.order_count,
                    "total_revenue": float(row.order_revenue),
                    "paid_amount": float(row.order_paid),
                    "pending_amount": float(row.order_pending),
                }

            for row in svc_rows:
                owner_id = str(row.owner_id)
                ws_id = str(row.id)
                key = get_ws_key(owner_id, ws_id)
                if key in merged:
                    merged[key]["sales_count"] += row.svc_count
                    merged[key]["total_revenue"] += float(row.svc_revenue)
                    merged[key]["paid_amount"] += float(row.svc_paid)
                    merged[key]["pending_amount"] += float(row.svc_pending)
                else:
                    merged[key] = {
                        "owner_id": owner_id,
                        "owner_name": f"{row.first_name} {row.last_name}".strip(),
                        "ws_id": ws_id,
                        "ws_name": row.name,
                        "sales_count": row.svc_count,
                        "total_revenue": float(row.svc_revenue),
                        "paid_amount": float(row.svc_paid),
                        "pending_amount": float(row.svc_pending),
                    }

            # Group by owner
            owners_map: dict[str, dict] = {}
            for data in merged.values():
                oid = data["owner_id"]
                if oid not in owners_map:
                    owners_map[oid] = {
                        "owner_id": oid,
                        "owner_name": data["owner_name"],
                        "total_sales": 0,
                        "total_revenue": 0.0,
                        "total_paid": 0.0,
                        "total_pending": 0.0,
                        "workshops": [],
                    }
                ow = owners_map[oid]
                ow["total_sales"] += data["sales_count"]
                ow["total_revenue"] += data["total_revenue"]
                ow["total_paid"] += data["paid_amount"]
                ow["total_pending"] += data["pending_amount"]
                ow["workshops"].append(
                    AdminWorkshopEarningsDTO(
                        workshop_id=data["ws_id"],
                        workshop_name=data["ws_name"],
                        sales_count=data["sales_count"],
                        total_revenue=data["total_revenue"],
                        paid_amount=data["paid_amount"],
                        pending_amount=data["pending_amount"],
                    )
                )

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminEarningsListDTO(owners=[
                    AdminOwnerEarningsDTO(**ow_data) for ow_data in owners_map.values()
                ]),
            )

        # --- Users ---

        class AdminUserListDTO(BaseModel):
            users: list[UserDTO]

        @self._router.get("/users", response_model=CoreResponse[AdminUserListDTO])
        async def list_users(
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            search: str | None = Query(default=None),
            current_user: CurrentUser = Depends(require_admin),
        ):
            is_superadmin = "SUPERADMIN" in current_user.roles
            async with get_session() as session:
                stmt = (
                    select(UserModel)
                    .where(UserModel.deleted_at.is_(None))
                )
                if search:
                    pattern = f"%{search}%"
                    stmt = stmt.where(
                        UserModel.first_name.ilike(pattern) |
                        UserModel.last_name.ilike(pattern) |
                        UserModel.email.ilike(pattern) |
                        UserModel.ci.ilike(pattern)
                    )
                stmt = stmt.offset(offset).limit(limit).order_by(UserModel.created_at.desc())
                r = await session.execute(stmt)
                all_users = r.unique().scalars().all()
                # SUPERADMIN sees all users except other SUPERADMINs; ADMIN cannot see ADMINs or SUPERADMINs
                if is_superadmin:
                    users = [
                        u
                        for u in all_users
                        if not any(str(role.role_id) == ROLE_NAME_TO_UUID["SUPERADMIN"] for role in u.roles)
                    ]
                else:
                    users = [
                        u
                        for u in all_users
                        if not any(
                            str(role.role_id) in (ROLE_NAME_TO_UUID["ADMIN"], ROLE_NAME_TO_UUID["SUPERADMIN"])
                            for role in u.roles
                        )
                    ]

            _mapper = UserMapper()
            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminUserListDTO(
                    users=[user_to_dto(u) for u in users]
                ),
            )

        @self._router.get("/users/{id}", response_model=CoreResponse[UserDTO])
        async def get_user(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get(str(id))
                if not user:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado")
            return CoreResponse(
                success=True,
                status_code=200,
                content=user_to_dto(user),
            )

        @self._router.put("/users/{id}", response_model=CoreResponse[UserDTO])
        async def update_user(
            id: UUID,
            body: AdminUpdateUserRequest,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get(str(id))
                if not user:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado")

                if body.first_name is not None:
                    user.first_name = body.first_name
                if body.last_name is not None:
                    user.last_name = body.last_name
                if body.phone is not None:
                    user.phone = body.phone
                if body.roles is not None:
                    # Prevent assigning ADMIN role through admin panel
                    if "ADMIN" in body.roles:
                        raise HTTPException(
                            status_code=400,
                            detail="No puedes asignar el rol de administrador",
                        )
                    old_roles = {r.role for r in user.roles}
                    new_roles = set(body.roles)
                    had_owner = "WORKSHOP_OWNER" in old_roles
                    has_owner = "WORKSHOP_OWNER" in new_roles

                    # Remove existing roles and set new ones
                    for r in list(user.roles):
                        await session.delete(r)
                    for role_name in body.roles:
                        user.roles.append(
                            UserRoleModel(role=role_name, user_id=user.id)
                        )

                    # If WORKSHOP_OWNER was removed — uncertify all their workshops
                    if had_owner and not has_owner:
                        workshop_stmt = select(WorkshopModel).where(
                            WorkshopModel.owner_id == id,
                            WorkshopModel.deleted_at.is_(None),
                        )
                        ws_r = await session.execute(workshop_stmt)
                        for w in ws_r.scalars().all():
                            w.was_certified = w.is_certified
                            w.is_certified = 0

                    # If WORKSHOP_OWNER was added back — restore previous certification
                    if not had_owner and has_owner:
                        workshop_stmt = select(WorkshopModel).where(
                            WorkshopModel.owner_id == id,
                            WorkshopModel.deleted_at.is_(None),
                        )
                        ws_r = await session.execute(workshop_stmt)
                        for w in ws_r.scalars().all():
                            w.is_certified = w.was_certified
                            w.was_certified = 0
                if body.is_suspended is not None:
                    user.is_suspended = body.is_suspended

                await session.commit()
                await session.refresh(user)

            return CoreResponse(
                success=True,
                status_code=200,
                message="Usuario actualizado exitosamente",
                content=user_to_dto(user),
            )

        @self._router.delete("/users/{id}", response_model=CoreResponse)
        async def delete_user(
            id: UUID,
            response: Response,
            force: bool = Query(default=False),
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get(str(id))
                if not user:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado")
                open_orders = await _count_open_orders(session, "users", id)
                if open_orders > 0 and not force:
                    raise HTTPException(
                        status_code=400,
                        detail=f"El usuario tiene {open_orders} ordenes activas. Usa force=true para eliminar de todas formas.",
                    )
                now = datetime.now(timezone.utc)

                # Cascade soft-delete: orders (as buyer)
                orders_stmt = select(OrderModel).where(OrderModel.user_id == id, OrderModel.deleted_at.is_(None))
                for o in (await session.execute(orders_stmt)).scalars().all():
                    o.deleted_at = now
                    for inst in list(o.installments):
                        inst.deleted_at = now
                    for item in list(o.items):
                        item.deleted_at = now

                # Cascade soft-delete: service orders
                so_stmt = select(ServiceOrderModel).where(ServiceOrderModel.user_id == id)
                for so in (await session.execute(so_stmt)).scalars().all():
                    so.status = "CANCELLED"

                # Soft-delete: vehicles
                veh_stmt = select(VehicleModel).where(VehicleModel.owner_id == id, VehicleModel.deleted_at.is_(None))
                for v in (await session.execute(veh_stmt)).scalars().all():
                    v.deleted_at = now

                # Soft-delete: workshops owned by user
                ws_stmt = select(WorkshopModel).where(WorkshopModel.owner_id == id, WorkshopModel.deleted_at.is_(None))
                for ws in (await session.execute(ws_stmt)).scalars().all():
                    ws.deleted_at = now
                    for p in (await session.execute(select(PartModel).where(PartModel.workshop_id == ws.id))).scalars().all():
                        p.deleted_at = now
                    for s in (await session.execute(select(WorkshopServiceModel).where(WorkshopServiceModel.workshop_id == ws.id))).scalars().all():
                        s.deleted_at = now

                # Delete: roles, cart, trusted devices, payment accounts, credit history, reviews
                for r in (await session.execute(select(UserRoleModel).where(UserRoleModel.user_id == id))).scalars().all():
                    await session.delete(r)
                for c in (await session.execute(select(CartModel).where(CartModel.user_id == id))).scalars().all():
                    await session.delete(c)
                for td in (await session.execute(select(TrustedDeviceModel).where(TrustedDeviceModel.user_id == id))).scalars().all():
                    await session.delete(td)
                for upa in (await session.execute(select(UserPaymentAccountModel).where(UserPaymentAccountModel.user_id == id))).scalars().all():
                    await session.delete(upa)
                for ch in (await session.execute(select(CreditHistoryModel).where(CreditHistoryModel.user_id == id))).scalars().all():
                    await session.delete(ch)
                for rv in (await session.execute(select(ReviewModel).where(ReviewModel.user_id == id))).scalars().all():
                    await session.delete(rv)
                for clr in (await session.execute(select(CreditLimitReviewModel).where(CreditLimitReviewModel.user_id == id))).scalars().all():
                    await session.delete(clr)
                for lf in (await session.execute(select(LateFeeModel).where(LateFeeModel.user_id == id))).scalars().all():
                    await session.delete(lf)

                user.deleted_at = now
                await session.commit()
            return CoreResponse(
                success=True, status_code=200, message="Usuario eliminado exitosamente"
            )

        # --- Workshops ---

        @self._router.get(
            "/workshops", response_model=CoreResponse[AdminWorkshopListDTO]
        )
        async def list_workshops(
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            search: str | None = Query(default=None),
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                stmt = (
                    select(WorkshopModel, UserModel.first_name, UserModel.last_name)
                    .join(UserModel, WorkshopModel.owner_id == UserModel.id)
                    .where(WorkshopModel.deleted_at.is_(None))
                )
                if search:
                    pattern = f"%{search}%"
                    stmt = stmt.where(
                        WorkshopModel.name.ilike(pattern) |
                        WorkshopModel.rif.ilike(pattern) |
                        UserModel.first_name.ilike(pattern) |
                        UserModel.last_name.ilike(pattern)
                    )
                stmt = stmt.offset(offset).limit(limit).order_by(WorkshopModel.created_at.desc())
                r = await session.execute(stmt)
                rows = r.all()

            def to_dto(ws, fn, ln):
                return AdminWorkshopDTO(
                    id=str(ws.id),
                    owner_id=str(ws.owner_id),
                    owner_name=f"{fn} {ln}".strip(),
                    name=ws.name,
                    rif=ws.rif,
                    address=ws.address,
                    is_certified=ws.is_certified,
                    is_suspended=ws.is_suspended,
                    average_rating=ws.average_rating,
                    verification_document_url=ws.verification_document_url,
                    photo_url=ws.photo_url,
                    created_at=ws.created_at.isoformat() if ws.created_at else "",
                )

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminWorkshopListDTO(
                    workshops=[to_dto(ws, fn, ln) for ws, fn, ln in rows]
                ),
            )

        @self._router.put("/workshops/{id}", response_model=CoreResponse[WorkshopDTO])
        async def update_workshop(
            id: UUID,
            body: AdminUpdateWorkshopRequest,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                repo = WorkshopRepository(session)
                workshop = await repo.get(str(id))
                if not workshop:
                    raise HTTPException(status_code=404, detail="Taller no encontrado")

                if body.name is not None:
                    workshop.name = body.name
                if body.address is not None:
                    workshop.address = body.address
                if body.rif is not None:
                    workshop.rif = body.rif
                if body.is_certified is not None:
                    workshop.is_certified = body.is_certified
                if body.is_suspended is not None:
                    workshop.is_suspended = body.is_suspended

                await session.commit()
                await session.refresh(workshop)

            return CoreResponse(
                success=True,
                status_code=200,
                message="Taller actualizado exitosamente",
                content=WorkshopDTO.model_validate(workshop),
            )

        @self._router.delete("/workshops/{id}", response_model=CoreResponse)
        async def delete_workshop(
            id: UUID,
            force: bool = Query(default=False),
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                workshop = await session.get(WorkshopModel, id)
                if not workshop:
                    raise HTTPException(status_code=404, detail="Taller no encontrado")

                open_orders = await _count_open_orders(session, "workshops", id)
                if open_orders > 0 and not force:
                    raise HTTPException(
                        status_code=400,
                        detail=f"El taller tiene {open_orders} órdenes activas. Usa force=true para eliminar de todas formas.",
                    )

                now = datetime.now(timezone.utc)
                workshop.deleted_at = now

                # Soft delete parts
                parts_stmt = select(PartModel).where(PartModel.workshop_id == id)
                parts_r = await session.execute(parts_stmt)
                for p in parts_r.scalars().all():
                    p.deleted_at = now

                # Soft delete services
                svc_stmt = select(WorkshopServiceModel).where(
                    WorkshopServiceModel.workshop_id == id
                )
                svc_r = await session.execute(svc_stmt)
                for s in svc_r.scalars().all():
                    s.deleted_at = now

                # Cascade: cancel service orders
                so_stmt = select(ServiceOrderModel).where(ServiceOrderModel.workshop_id == id)
                for so in (await session.execute(so_stmt)).scalars().all():
                    so.status = "CANCELLED"

                # Cascade: soft-delete orders containing items from this workshop
                oi_stmt = select(OrderItemModel.order_id).where(OrderItemModel.workshop_id == id, OrderItemModel.deleted_at.is_(None))
                order_ids = [row[0] for row in (await session.execute(oi_stmt)).all()]
                if order_ids:
                    for o in (await session.execute(select(OrderModel).where(OrderModel.id.in_(order_ids)))).scalars().all():
                        o.deleted_at = now
                        for inst in list(o.installments):
                            inst.deleted_at = now
                        for item in list(o.items):
                            if item.workshop_id == id:
                                item.deleted_at = now

                # Delete: reviews, commissions, bank accounts, mobile payments, payment methods
                for rv in (await session.execute(select(ReviewModel).where(ReviewModel.workshop_id == id))).scalars().all():
                    await session.delete(rv)
                for wc in (await session.execute(select(WorkshopCommissionModel).where(WorkshopCommissionModel.workshop_id == id))).scalars().all():
                    await session.delete(wc)

                await session.commit()

            return CoreResponse(
                success=True,
                status_code=200,
                message="Taller eliminado exitosamente",
            )

        # --- Parts ---

        @self._router.get("/parts", response_model=CoreResponse[AdminPartListDTO])
        async def list_parts(
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            search: str | None = Query(default=None),
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                stmt = (
                    select(PartModel, WorkshopModel.name)
                    .join(WorkshopModel, WorkshopModel.id == PartModel.workshop_id)
                    .where(PartModel.deleted_at.is_(None))
                )
                if search:
                    pattern = f"%{search}%"
                    stmt = stmt.where(
                        PartModel.name.ilike(pattern) |
                        WorkshopModel.name.ilike(pattern) |
                        PartModel.condition.ilike(pattern) |
                        PartModel.category.ilike(pattern)
                    )
                stmt = stmt.offset(offset).limit(limit).order_by(PartModel.created_at.desc())
                r = await session.execute(stmt)
                rows = r.all()

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminPartListDTO(parts=[
                    AdminPartDTO(
                        id=p.id,
                        workshop_id=p.workshop_id,
                        workshop_name=wn,
                        name=p.name,
                        description=p.description,
                        price=p.price,
                        stock=p.stock,
                        condition=p.condition,
                        category=p.category,
                        allows_installments=p.allows_installments,
                        installment_min_percentage=p.installment_min_percentage,
                        photo_url=p.photo_url,
                        is_active=p.is_active,
                        created_at=p.created_at,
                    )
                    for p, wn in rows
                ]),
            )

        @self._router.put("/parts/{id}", response_model=CoreResponse[PartDTO])
        async def update_part(
            id: UUID,
            body: AdminPartUpdateRequest,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                part = await session.get(PartModel, id)
                if not part:
                    raise HTTPException(
                        status_code=404, detail="Repuesto no encontrado"
                    )
                if body.name is not None:
                    part.name = body.name
                if body.price is not None:
                    part.price = body.price
                if body.stock is not None:
                    part.stock = body.stock
                if body.is_active is not None:
                    part.is_active = body.is_active
                await session.commit()
                await session.refresh(part)

            return CoreResponse(
                success=True,
                status_code=200,
                message="Repuesto actualizado exitosamente",
                content=PartDTO.model_validate(part),
            )

        @self._router.delete("/parts/{id}", response_model=CoreResponse)
        async def delete_part(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                part = await session.get(PartModel, id)
                if not part:
                    raise HTTPException(
                        status_code=404, detail="Repuesto no encontrado"
                    )
                part.deleted_at = datetime.now(timezone.utc)
                await session.commit()

            return CoreResponse(
                success=True,
                status_code=200,
                message="Repuesto eliminado exitosamente",
            )

        # --- Vehicles ---

        class AdminVehicleDTO(BaseModel):
            id: str
            owner_id: str
            owner_name: str | None = None
            owner_ci: str | None = None
            owner_email: str | None = None
            vehicle_type: str
            brand: str
            model: str
            year: int
            license_plate: str
            vin: str
            photo_url: str | None = None
            is_active: int
            created_at: str

        class AdminVehicleListDTO(BaseModel):
            vehicles: list[AdminVehicleDTO]

        @self._router.get("/vehicles", response_model=CoreResponse[AdminVehicleListDTO])
        async def list_vehicles(
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            search: str | None = Query(default=None),
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                stmt = (
                    select(VehicleModel, UserModel)
                    .join(UserModel, VehicleModel.owner_id == UserModel.id)
                    .where(VehicleModel.deleted_at.is_(None))
                )
                if search:
                    pattern = f"%{search}%"
                    stmt = stmt.where(
                        VehicleModel.vehicle_type.ilike(pattern) |
                        VehicleModel.license_plate.ilike(pattern) |
                        VehicleModel.model.ilike(pattern) |
                        VehicleModel.brand.ilike(pattern) |
                        UserModel.first_name.ilike(pattern) |
                        UserModel.last_name.ilike(pattern) |
                        UserModel.ci.ilike(pattern)
                    )
                stmt = stmt.offset(offset).limit(limit).order_by(VehicleModel.created_at.desc())
                r = await session.execute(stmt)
                rows = r.unique().all()

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminVehicleListDTO(
                    vehicles=[
                        AdminVehicleDTO(
                            id=str(v.id),
                            owner_id=str(v.owner_id),
                            owner_name=f"{u.first_name} {u.last_name}".strip(),
                            owner_ci=u.ci,
                            owner_email=u.email,
                            vehicle_type=v.vehicle_type,
                            brand=v.brand,
                            model=v.model,
                            year=v.year,
                            license_plate=v.license_plate,
                            vin=v.vin,
                            photo_url=v.photo_url,
                            is_active=v.is_active,
                            created_at=v.created_at.isoformat() if v.created_at else "",
                        )
                        for v, u in rows
                    ]
                ),
            )

        # --- Orders ---

        class AdminOrderDTO(BaseModel):
            id: str
            user_id: str
            buyer_name: str
            buyer_ci: str | None
            vehicle_id: str | None
            workshop_name: str
            mileage: int
            total_amount: float
            status: str
            payment_status: str
            payment_type: str  # CONTADO or FINANCIADO
            installment_count: int
            installments_paid: int
            installments_pending_verification: int
            installments_pending: int
            created_at: str

        class AdminOrderListDTO(BaseModel):
            orders: list[AdminOrderDTO]

        @self._router.get("/orders", response_model=CoreResponse[AdminOrderListDTO])
        async def list_orders(
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            search: str | None = Query(default=None),
            status: str | None = Query(default=None),
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                stmt = (
                    select(
                        OrderModel,
                        UserModel.first_name,
                        UserModel.last_name,
                        UserModel.ci,
                        WorkshopModel.name,
                    )
                    .options(selectinload(OrderModel.installments))
                    .join(UserModel, UserModel.id == OrderModel.user_id)
                    .join(OrderItemModel, OrderItemModel.order_id == OrderModel.id)
                    .join(WorkshopModel, WorkshopModel.id == OrderItemModel.workshop_id)
                    .where(OrderModel.deleted_at.is_(None))
                )
                if search:
                    pattern = f"%{search}%"
                    stmt = stmt.where(
                        UserModel.first_name.ilike(pattern) |
                        UserModel.last_name.ilike(pattern) |
                        WorkshopModel.name.ilike(pattern) |
                        UserModel.ci.ilike(pattern) |
                        OrderModel.id.cast(str).ilike(pattern)
                    )
                if status == "PENDING":
                    stmt = stmt.where(OrderModel.status.notin_(["RECEIVED", "CANCELLED", "CLOSED"]))
                elif status == "CLOSED":
                    stmt = stmt.where(OrderModel.status.in_(["RECEIVED", "CANCELLED", "CLOSED"]))
                stmt = stmt.order_by(OrderModel.created_at.desc()).offset(offset).limit(limit)
                r = await session.execute(stmt)
                rows = r.all()

                # Deduplicate by order id (join with items may produce duplicates)
                seen = set()
                orders_data = []
                for o, fn, ln, ci, wn in rows:
                    key = str(o.id)
                    if key not in seen:
                        seen.add(key)
                        orders_data.append((o, fn, ln, ci, wn))

                # Build order DTOs with installment stats
                order_dtos = []
                for o, fn, ln, ci, wn in orders_data:
                    insts = o.installments or []
                    inst_paid = sum(1 for i in insts if i.status == "PAID")
                    inst_pending_verif = sum(1 for i in insts if i.status == "PENDING_VERIFICATION")
                    inst_pending = sum(1 for i in insts if i.status in ("PENDING", "OVERDUE"))
                    payment_type = "FINANCIADO" if len(insts) > 1 else "CONTADO"

                    order_dtos.append(AdminOrderDTO(
                        id=str(o.id),
                        user_id=str(o.user_id),
                        buyer_name=f"{fn} {ln}".strip(),
                        buyer_ci=ci,
                        vehicle_id=str(o.vehicle_id) if o.vehicle_id else None,
                        workshop_name=wn,
                        mileage=o.mileage,
                        total_amount=o.total_amount,
                        status="CLOSED" if o.status in ("RECEIVED", "CANCELLED", "CLOSED") else "PENDING",
                        payment_status=o.status,
                        payment_type=payment_type,
                        installment_count=len(insts),
                        installments_paid=inst_paid,
                        installments_pending_verification=inst_pending_verif,
                        installments_pending=inst_pending,
                        created_at=o.created_at.isoformat() if o.created_at else "",
                    ))

                return CoreResponse(
                    success=True,
                    status_code=200,
                    content=AdminOrderListDTO(orders=order_dtos),
                )

        # -- Admin Service Orders --

        class AdminServiceOrderDTO(BaseModel):
            id: str
            user_id: str
            workshop_id: str
            service_name: str
            workshop_name: str
            vehicle_brand: str
            vehicle_model: str
            owner_first_name: str | None = None
            owner_last_name: str | None = None
            owner_ci: str | None = None
            status: str
            base_price: float
            final_price: float | None
            created_at: str

        class AdminServiceOrderListDTO(BaseModel):
            service_orders: list[AdminServiceOrderDTO]

        @self._router.get("/service-orders", response_model=CoreResponse[AdminServiceOrderListDTO])
        async def list_service_orders(
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            search: str = Query(default=None),
            status: str = Query(default=None),
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                stmt = (
                    select(ServiceOrderModel)
                    .options(
                        selectinload(ServiceOrderModel.workshop_service),
                        selectinload(ServiceOrderModel.workshop),
                        selectinload(ServiceOrderModel.vehicle),
                        selectinload(ServiceOrderModel.user),
                    )
                    .join(WorkshopModel, ServiceOrderModel.workshop_id == WorkshopModel.id)
                    .join(VehicleModel, ServiceOrderModel.vehicle_id == VehicleModel.id)
                    .join(UserModel, ServiceOrderModel.user_id == UserModel.id)
                )

                # Apply filters
                if search:
                    stmt = stmt.where(
                        (ServiceOrderModel.id.ilike(f"%{search}%")) |
                        (WorkshopModel.name.ilike(f"%{search}%")) |
                        (VehicleModel.brand.ilike(f"%{search}%")) |
                        (VehicleModel.model.ilike(f"%{search}%")) |
                        (UserModel.first_name.ilike(f"%{search}%")) |
                        (UserModel.last_name.ilike(f"%{search}%")) |
                        (UserModel.ci.ilike(f"%{search}%"))
                    )

                if status:
                    status_groups = {
                        "activo": ["PENDING", "DROPPED_OFF", "AT_WORKSHOP", "REVISION_SENT", "QUOTED", "REJECTED", "ACCEPTED", "IN_PROGRESS", "COMPLETED", "SHIPPED", "DELIVERED"],
                        "finalizado": ["CLOSED", "CANCELLED"],
                    }
                    if status in status_groups:
                        stmt = stmt.where(ServiceOrderModel.status.in_(status_groups[status]))
                    else:
                        stmt = stmt.where(ServiceOrderModel.status == status)

                stmt = (
                    stmt
                    .offset(offset)
                    .limit(limit)
                    .order_by(ServiceOrderModel.created_at.desc())
                )
                r = await session.execute(stmt)
                orders = r.scalars().all()

                return CoreResponse(
                    success=True,
                    status_code=200,
                    content=AdminServiceOrderListDTO(service_orders=[
                        AdminServiceOrderDTO(
                            id=str(o.id),
                            user_id=str(o.user_id),
                            workshop_id=str(o.workshop_id),
                            service_name=o.workshop_service.service_name if o.workshop_service else "",
                            workshop_name=o.workshop.name if o.workshop else "",
                            vehicle_brand=o.vehicle.brand if o.vehicle else "",
                            vehicle_model=o.vehicle.model if o.vehicle else "",
                            owner_first_name=o.user.first_name if o.user else None,
                            owner_last_name=o.user.last_name if o.user else None,
                            owner_ci=o.user.ci if o.user else None,
                            status=o.status,
                            base_price=o.base_price,
                            final_price=o.final_price,
                            created_at=o.created_at.isoformat() if o.created_at else "",
                        )
                        for o in orders
                    ]),
                )

        @self._router.put("/vehicles/{id}", response_model=CoreResponse[VehicleDTO])
        async def update_vehicle(
            id: UUID,
            body: AdminVehicleUpdateRequest,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                vehicle = await session.get(VehicleModel, id)
                if not vehicle:
                    raise HTTPException(
                        status_code=404, detail="Vehículo no encontrado"
                    )
                if body.brand is not None:
                    vehicle.brand = body.brand
                if body.model is not None:
                    vehicle.model = body.model
                if body.year is not None:
                    vehicle.year = body.year
                if body.license_plate is not None:
                    vehicle.license_plate = body.license_plate
                if body.vehicle_type is not None:
                    vehicle.vehicle_type = body.vehicle_type
                if body.is_active is not None:
                    vehicle.is_active = body.is_active
                await session.commit()
                await session.refresh(vehicle)

            return CoreResponse(
                success=True,
                status_code=200,
                message="Vehículo actualizado exitosamente",
                content=VehicleDTO.model_validate(vehicle),
            )

        @self._router.delete("/vehicles/{id}", response_model=CoreResponse)
        async def delete_vehicle(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                vehicle = await session.get(VehicleModel, id)
                if not vehicle:
                    raise HTTPException(
                        status_code=404, detail="Vehículo no encontrado"
                    )

                # Check for open orders
                open_orders = await _count_open_orders(session, "vehicles", id)
                if open_orders > 0:
                    raise HTTPException(
                        status_code=400,
                        detail="No se puede eliminar el vehículo porque tiene órdenes activas.",
                    )

                vehicle.deleted_at = datetime.now(timezone.utc)
                await session.commit()

            return CoreResponse(
                success=True,
                status_code=200,
                message="Vehículo eliminado exitosamente",
            )

        @self._router.delete("/orders/{id}", response_model=CoreResponse)
        async def delete_order(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                order = await session.get(OrderModel, id)
                if not order:
                    raise HTTPException(status_code=404, detail="Orden no encontrada")
                now = datetime.now(timezone.utc)
                for inst in list(order.installments):
                    inst.deleted_at = now
                for item in list(order.items):
                    item.deleted_at = now
                order.deleted_at = now
                # Delete related: transactions, reviews, commissions, vehicle history
                for t in (await session.execute(select(TransactionModel).where(TransactionModel.order_id == id))).scalars().all():
                    await session.delete(t)
                for rv in (await session.execute(select(OrderReviewModel).where(OrderReviewModel.order_id == id))).scalars().all():
                    await session.delete(rv)
                for wc in (await session.execute(select(WorkshopCommissionModel).where(WorkshopCommissionModel.order_id == id))).scalars().all():
                    await session.delete(wc)
                for vhl in (await session.execute(select(VehicleHistoryLogModel).where(VehicleHistoryLogModel.order_id == id))).scalars().all():
                    await session.delete(vhl)
                await session.commit()

                return CoreResponse(
                    success=True,
                    status_code=200,
                    message="Orden eliminada exitosamente",
                )

        @self._router.post("/orders/{id}/force-close", response_model=CoreResponse)
        async def force_close_order(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                order = await session.get(OrderModel, id)
                if not order:
                    raise HTTPException(status_code=404, detail="Orden no encontrada")
                # Mark all installments as paid
                for inst in list(order.installments):
                    if inst.status not in ("PAID",):
                        inst.status = "PAID"
                        if not inst.paid_at:
                            inst.paid_at = datetime.now(timezone.utc)
                # Close the order
                order.status = "CLOSED"
                order.closed_by_client = True
                order.closed_by_workshop = True
                await session.commit()

                return CoreResponse(
                    success=True,
                    status_code=200,
                    message="Orden cerrada y marcada como pagada exitosamente",
                )

        @self._router.delete("/service-orders/{id}", response_model=CoreResponse)
        async def delete_service_order(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                so = await session.get(ServiceOrderModel, id)
                if not so:
                    raise HTTPException(status_code=404, detail="Orden de servicio no encontrada")
                # Delete related: payments, installments, commissions
                for p in (await session.execute(select(ServiceOrderPaymentModel).where(ServiceOrderPaymentModel.service_order_id == id))).scalars().all():
                    await session.delete(p)
                for inst in (await session.execute(select(ServiceOrderInstallmentModel).where(ServiceOrderInstallmentModel.service_order_id == id))).scalars().all():
                    await session.delete(inst)
                for wc in (await session.execute(select(WorkshopCommissionModel).where(WorkshopCommissionModel.service_order_id == id))).scalars().all():
                    await session.delete(wc)
                await session.delete(so)
                await session.commit()

                return CoreResponse(
                    success=True,
                    status_code=200,
                    message="Orden de servicio eliminada exitosamente",
                )

        @self._router.patch("/orders/{id}/cancel", response_model=CoreResponse)
        async def cancel_order(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                order = await session.get(OrderModel, id)
                if not order:
                    raise HTTPException(status_code=404, detail="Orden no encontrada")
                if order.status in ["PAID", "CLOSED", "CANCELLED"]:
                    raise HTTPException(status_code=400, detail="No se puede cancelar una orden en este estado")
                
                order.status = "CANCELLED"
                await session.commit()
                
                return CoreResponse(
                    success=True,
                    status_code=200,
                    message="Orden cancelada exitosamente",
                )

        # --- Commissions ---

        class CommissionItemDTO(BaseModel):
            name: str
            quantity: int
            unit_price: float
            total: float

        class AdminCommissionDTO(BaseModel):
            id: str
            workshop_id: str
            workshop_name: str
            owner_id: str
            owner_name: str
            owner_email: str
            order_id: str | None = None
            service_order_id: str | None = None
            financed_amount: float
            commission_rate: float
            commission_amount: float
            period_month: int
            period_year: int
            status: str
            payment_method: str | None = None
            reference_number: str | None = None
            rate: float | None = None
            rate_date: str | None = None
            created_at: str
            paid_at: str | None = None
            items: list[CommissionItemDTO] = []

        class AdminCommissionListDTO(BaseModel):
            commissions: list[AdminCommissionDTO]
            total_pending: float
            total_paid: float

        @self._router.get("/commissions", response_model=CoreResponse[AdminCommissionListDTO])
        async def list_commissions(
            status: str | None = Query(default=None),
            workshop_id: UUID | None = Query(default=None),
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                stmt = (
                    select(
                        WorkshopCommissionModel,
                        WorkshopModel.name.label("workshop_name"),
                        WorkshopModel.owner_id,
                        UserModel.first_name.label("owner_first"),
                        UserModel.last_name.label("owner_last"),
                        UserModel.email.label("owner_email"),
                    )
                    .join(WorkshopModel, WorkshopModel.id == WorkshopCommissionModel.workshop_id)
                    .join(UserModel, UserModel.id == WorkshopModel.owner_id)
                )
                if status:
                    stmt = stmt.where(WorkshopCommissionModel.status == status)
                if workshop_id:
                    stmt = stmt.where(WorkshopCommissionModel.workshop_id == workshop_id)
                stmt = stmt.order_by(WorkshopCommissionModel.created_at.desc())
                r = await session.execute(stmt)
                rows = r.all()

                total_pending = sum(
                    row[0].commission_amount for row in rows if row[0].status in ("PENDING", "PENDING_VERIFICATION")
                )
                total_paid = sum(
                    row[0].commission_amount for row in rows if row[0].status == "PAID"
                )

                # Fetch order items for commissions with order_id
                order_ids = [row[0].order_id for row in rows if row[0].order_id]
                items_map: dict[UUID, list] = {}
                if order_ids:
                    items_stmt = (
                        select(OrderItemModel)
                        .where(OrderItemModel.order_id.in_(order_ids))
                    )
                    items_r = await session.execute(items_stmt)
                    for item in items_r.scalars().all():
                        items_map.setdefault(item.order_id, []).append(item)

                commissions_list = [
                        AdminCommissionDTO(
                            id=str(row[0].id),
                            workshop_id=str(row[0].workshop_id),
                            workshop_name=row.workshop_name,
                            owner_id=str(row.owner_id),
                            owner_name=f"{row.owner_first} {row.owner_last}",
                            owner_email=row.owner_email,
                            order_id=str(row[0].order_id) if row[0].order_id else None,
                            service_order_id=str(row[0].service_order_id) if row[0].service_order_id else None,
                            financed_amount=row[0].financed_amount,
                            commission_rate=row[0].commission_rate,
                            commission_amount=row[0].commission_amount,
                            period_month=row[0].period_month,
                            period_year=row[0].period_year,
                            status=row[0].status,
                            payment_method=row[0].payment_method,
                            reference_number=row[0].reference_number,
                            rate=row[0].rate,
                            rate_date=row[0].rate_date.isoformat() if row[0].rate_date else None,
                            created_at=row[0].created_at.isoformat() if row[0].created_at else "",
                            paid_at=row[0].paid_at.isoformat() if row[0].paid_at else None,
                            items=[
                                CommissionItemDTO(
                                    name=item.part_name or f"Item {item.id}",
                                    quantity=item.quantity,
                                    unit_price=item.unit_price,
                                    total=item.unit_price * item.quantity,
                                )
                                for item in items_map.get(row[0].order_id, [])
                            ] if row[0].order_id else [],
                        )
                        for row in rows
                    ]

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminCommissionListDTO(
                    commissions=commissions_list,
                    total_pending=round(total_pending, 2),
                    total_paid=round(total_paid, 2),
                ),
            )

        @self._router.patch("/commissions/{id}/mark-paid", response_model=CoreResponse)
        async def mark_commission_paid(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                commission = await session.get(WorkshopCommissionModel, id)
                if not commission:
                    raise HTTPException(status_code=404, detail="Comisión no encontrada")
                if commission.status == "PAID":
                    raise HTTPException(status_code=400, detail="La comisión ya está pagada")
                if commission.status not in ("PENDING", "PENDING_VERIFICATION"):
                    raise HTTPException(status_code=400, detail="La comisión no está pendiente de verificación")
                commission.status = "PAID"
                commission.paid_at = datetime.now(timezone.utc)
                # Check if this was the last pending commission for this workshop
                from sqlalchemy import select as _sel2, func as _func2
                remaining = await session.scalar(
                    _sel2(_func2.count(WorkshopCommissionModel.id)).where(
                        WorkshopCommissionModel.workshop_id == commission.workshop_id,
                        WorkshopCommissionModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                    )
                )
                if remaining is not None and remaining <= 0:
                    ws_model = await session.get(WorkshopModel, commission.workshop_id)
                    if ws_model:
                        ws_model.commission_suspended = 0
                        ws_model.is_suspended = 0
                        ws_model.commission_warned_at = None
                await session.commit()

            # Notify workshop owner
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_verified_user
                from src.config.models import User as _U, Workshop as _W
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _ws = (await _s.execute(_sel(_W).where(_W.id == commission.workshop_id))).scalars().first()
                    if _ws:
                        _owner = (await _s.execute(_sel(_U).where(_U.id == _ws.owner_id))).scalars().first()
                        if _owner:
                            await send_email(
                                _owner.email,
                                "Comisión verificada - AutoTech",
                                payment_verified_user(
                                    f"{_owner.first_name} {_owner.last_name}",
                                    "Comisión de taller",
                                    commission.commission_amount,
                                    lang=_owner.language_preference or "es",
                                ),
                            )
            except Exception:
                pass

            return CoreResponse(
                success=True,
                status_code=200,
                message="Comisión verificada",
            )

        @self._router.get("/commissions/cutoff", response_model=CoreResponse)
        async def monthly_cutoff(
            month: int | None = Query(default=None, ge=1, le=12),
            year: int | None = Query(default=None, ge=2020, le=2100),
            _: CurrentUser = Depends(require_superadmin),
        ):
            """Get monthly cutoff summary: total commissions per workshop for a given period."""
            now = datetime.now(timezone.utc)
            target_month = month or now.month
            target_year = year or now.year

            async with get_session() as session:
                stmt = (
                    select(
                        WorkshopCommissionModel.workshop_id,
                        WorkshopModel.name,
                        func.count(WorkshopCommissionModel.id).label("count"),
                        func.coalesce(func.sum(WorkshopCommissionModel.commission_amount), 0).label("total"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (WorkshopCommissionModel.status.in_(["PENDING", "PENDING_VERIFICATION"]), WorkshopCommissionModel.commission_amount),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("pending"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (WorkshopCommissionModel.status == "PAID", WorkshopCommissionModel.commission_amount),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("paid"),
                    )
                    .join(WorkshopModel, WorkshopModel.id == WorkshopCommissionModel.workshop_id)
                    .where(
                        WorkshopCommissionModel.period_month == target_month,
                        WorkshopCommissionModel.period_year == target_year,
                    )
                    .group_by(
                        WorkshopCommissionModel.workshop_id,
                        WorkshopModel.name,
                    )
                )
                r = await session.execute(stmt)
                rows = r.all()

            class CutoffWorkshopDTO(BaseModel):
                workshop_id: str
                workshop_name: str
                commission_count: int
                total_amount: float
                pending_amount: float
                paid_amount: float

            class CutoffSummaryDTO(BaseModel):
                period_month: int
                period_year: int
                workshops: list[CutoffWorkshopDTO]
                grand_total: float
                grand_pending: float
                grand_paid: float

            workshops = [
                CutoffWorkshopDTO(
                    workshop_id=str(row.workshop_id),
                    workshop_name=row.name,
                    commission_count=row.count,
                    total_amount=float(row.total),
                    pending_amount=float(row.pending),
                    paid_amount=float(row.paid),
                )
                for row in rows
            ]

            return CoreResponse(
                success=True,
                status_code=200,
                content=CutoffSummaryDTO(
                    period_month=target_month,
                    period_year=target_year,
                    workshops=workshops,
                    grand_total=round(sum(w.total_amount for w in workshops), 2),
                    grand_pending=round(sum(w.pending_amount for w in workshops), 2),
                    grand_paid=round(sum(w.paid_amount for w in workshops), 2),
                ),
            )

        # --- Late Fees (Superadmin) ---

        class AdminLateFeeDTO(BaseModel):
            id: str
            user_id: str
            user_name: str
            user_email: str
            installment_type: str
            installment_id: str
            amount: float
            status: str
            payment_method: str
            reference_number: str | None = None
            rate: float | None = None
            rate_date: str | None = None
            paid_at: str | None = None
            erroneous_note: str | None = None
            created_at: str

        class AdminLateFeeListDTO(BaseModel):
            late_fees: list[AdminLateFeeDTO]
            total_pending: float
            total_paid: float

        @self._router.get("/late-fees", response_model=CoreResponse[AdminLateFeeListDTO])
        async def admin_list_late_fees(
            status: str | None = Query(default=None),
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import LateFee as LateFeeModel
            async with get_session() as session:
                stmt = (
                    select(LateFeeModel, UserModel.first_name, UserModel.last_name, UserModel.email)
                    .join(UserModel, UserModel.id == LateFeeModel.user_id)
                )
                if status:
                    stmt = stmt.where(LateFeeModel.status == status)
                stmt = stmt.order_by(LateFeeModel.created_at.desc())
                r = await session.execute(stmt)
                rows = r.all()

                total_pending = sum(f.amount for f, _, _, _ in rows if f.status in ("PENDING", "PENDING_VERIFICATION"))
                total_paid = sum(f.amount for f, _, _, _ in rows if f.status == "PAID")

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminLateFeeListDTO(
                    late_fees=[
                        AdminLateFeeDTO(
                            id=str(f.id),
                            user_id=str(f.user_id),
                            user_name=f"{fn} {ln}",
                            user_email=em,
                            installment_type=f.installment_type,
                            installment_id=str(f.installment_id),
                            amount=f.amount,
                            status=f.status,
                            payment_method=f.payment_method,
                            reference_number=f.reference_number,
                            rate=f.rate,
                            rate_date=f.rate_date.isoformat() if f.rate_date else None,
                            paid_at=f.paid_at.isoformat() if f.paid_at else None,
                            erroneous_note=f.erroneous_note,
                            created_at=f.created_at.isoformat() if f.created_at else "",
                        )
                        for f, fn, ln, em in rows
                    ],
                    total_pending=round(total_pending, 2),
                    total_paid=round(total_paid, 2),
                ),
            )

        class MarkLateFeePaidRequest(BaseModel):
            payment_method: str = "OTHER"
            reference_number: str | None = None

        @self._router.patch("/late-fees/{id}/mark-paid", response_model=CoreResponse)
        async def admin_mark_late_fee_paid(
            id: UUID,
            body: MarkLateFeePaidRequest,
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import LateFee as LateFeeModel
            async with get_session() as session:
                fee = await session.get(LateFeeModel, id)
                if not fee:
                    raise HTTPException(status_code=404, detail="Mora no encontrada")
                if fee.status == "PAID":
                    raise HTTPException(status_code=400, detail="La mora ya está pagada")
                fee.status = "PENDING_VERIFICATION"
                fee.payment_method = body.payment_method
                if body.reference_number:
                    fee.reference_number = body.reference_number
                await session.commit()

            # Send email to superadmin
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_registered_admin
                from src.config.models import User as _U
                from src.modules.users.infrastructure.auth import ROLE_NAME_TO_UUID as _RMAP
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _sa = (await _s.execute(_sel(_U).join(UserRoleModel, UserRoleModel.user_id == _U.id).where(UserRoleModel.role_id == _RMAP["SUPERADMIN"]))).scalars().first()
                    _payer = (await _s.execute(_sel(_U).where(_U.id == fee.user_id))).scalars().first()
                    if _sa and _payer:
                        await send_email(
                            _sa.email,
                            "Pago de mora registrado - AutoTech",
                            payment_registered_admin(
                                "Mora",
                                f"{_payer.first_name} {_payer.last_name}",
                                fee.amount,
                                body.payment_method,
                                body.reference_number,
                                lang=_sa.language_preference or "es",
                            ),
                        )
            except Exception:
                pass

            return CoreResponse(
                success=True,
                status_code=200,
                message="Pago de mora registrado. Pendiente de verificación.",
            )

        @self._router.patch("/late-fees/{id}/verify", response_model=CoreResponse)
        async def admin_verify_late_fee(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import LateFee as LateFeeModel
            async with get_session() as session:
                fee = await session.get(LateFeeModel, id)
                if not fee:
                    raise HTTPException(status_code=404, detail="Mora no encontrada")
                if fee.status not in ("PENDING", "PENDING_VERIFICATION"):
                    raise HTTPException(status_code=400, detail="La mora no está pendiente de verificación")
                fee.status = "PAID"
                fee.paid_at = datetime.now(timezone.utc)
                await session.commit()

            # Notify client
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_verified_user
                from src.config.models import User as _U
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _user = (await _s.execute(_sel(_U).where(_U.id == fee.user_id))).scalars().first()
                    if _user:
                        await send_email(
                            _user.email,
                            "Mora verificada - AutoTech",
                            payment_verified_user(
                                f"{_user.first_name} {_user.last_name}",
                                "Mora",
                                fee.amount,
                                lang=_user.language_preference or "es",
                            ),
                        )
            except Exception:
                pass

            return CoreResponse(
                success=True,
                status_code=200,
                message="Mora verificada",
            )

        @self._router.patch("/late-fees/{id}/mark-erroneous", response_model=CoreResponse)
        async def admin_mark_late_fee_erroneous(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import LateFee as LateFeeModel
            async with get_session() as session:
                fee = await session.get(LateFeeModel, id)
                if not fee:
                    raise HTTPException(status_code=404, detail="Mora no encontrada")
                if fee.status == "PAID":
                    raise HTTPException(status_code=400, detail="La mora ya está pagada")
                fee.status = "PENDING"
                fee.payment_method = "OTHER"
                fee.reference_number = None
                fee.paid_at = None
                await session.commit()

            # Notify client
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_rejected_user
                from src.config.models import User as _U
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _user = (await _s.execute(_sel(_U).where(_U.id == fee.user_id))).scalars().first()
                    if _user:
                        await send_email(
                            _user.email,
                            "Mora rechazada - AutoTech",
                            payment_rejected_user(
                                f"{_user.first_name} {_user.last_name}",
                                "Mora",
                                fee.amount,
                                lang=_user.language_preference or "es",
                            ),
                        )
            except Exception:
                pass

            return CoreResponse(
                success=True,
                status_code=200,
                message="Mora marcada como errónea. Puede volver a registrar el pago.",
            )

        # --- Commission payment registration (Superadmin) ---

        class RegisterCommissionPaymentRequest(BaseModel):
            payment_method: str = "BANK_TRANSFER"
            reference_number: str | None = None
            rate: float | None = None
            rate_date: str | None = None

        @self._router.patch("/commissions/{id}/register-payment", response_model=CoreResponse)
        async def register_commission_payment(
            id: UUID,
            body: RegisterCommissionPaymentRequest,
            _: CurrentUser = Depends(require_superadmin),
        ):
            """Superadmin registers a payment from a workshop for their commission."""
            async with get_session() as session:
                commission = await session.get(WorkshopCommissionModel, id)
                if not commission:
                    raise HTTPException(status_code=404, detail="Comisión no encontrada")
                if commission.status == "PAID":
                    raise HTTPException(status_code=400, detail="La comisión ya está pagada")
                commission.status = "PENDING_VERIFICATION"
                commission.payment_method = body.payment_method
                commission.reference_number = body.reference_number
                if body.rate is not None:
                    commission.rate = body.rate
                if body.rate_date:
                    try:
                        commission.rate_date = datetime.fromisoformat(body.rate_date)
                    except ValueError:
                        pass
                await session.commit()

            # Send email to superadmin
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_registered_admin
                from src.config.models import User as _U, Workshop as _W
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _sa = (await _s.execute(_sel(_U).join(UserRoleModel, UserRoleModel.user_id == _U.id).where(UserRoleModel.role_id == ROLE_NAME_TO_UUID["SUPERADMIN"]))).scalars().first()
                    _ws = (await _s.execute(_sel(_W.name).where(_W.id == commission.workshop_id))).scalars().first()
                    if _sa:
                        await send_email(
                            _sa.email,
                            "Pago de comisión registrado - AutoTech",
                            payment_registered_admin(
                                "Comisión de taller",
                                _ws or "N/A",
                                commission.commission_amount,
                                body.payment_method,
                                body.reference_number,
                                lang=_sa.language_preference or "es",
                            ),
                        )
            except Exception:
                pass

            return CoreResponse(
                success=True,
                status_code=200,
                message="Pago de comisión registrado. Pendiente de verificación.",
            )

        @self._router.patch("/commissions/{id}/mark-erroneous", response_model=CoreResponse)
        async def mark_commission_erroneous(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            async with get_session() as session:
                commission = await session.get(WorkshopCommissionModel, id)
                if not commission:
                    raise HTTPException(status_code=404, detail="Comisión no encontrada")
                if commission.status == "PAID":
                    raise HTTPException(status_code=400, detail="La comisión ya está pagada")
                commission.status = "PENDING"
                commission.payment_method = None
                commission.reference_number = None
                commission.paid_at = None
                await session.commit()

            # Notify workshop owner
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_rejected_user
                from src.config.models import User as _U, Workshop as _W
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _ws = (await _s.execute(_sel(_W).where(_W.id == commission.workshop_id))).scalars().first()
                    if _ws:
                        _owner = (await _s.execute(_sel(_U).where(_U.id == _ws.owner_id))).scalars().first()
                        if _owner:
                            await send_email(
                                _owner.email,
                                "Comisión rechazada - AutoTech",
                                payment_rejected_user(
                                    f"{_owner.first_name} {_owner.last_name}",
                                    "Comisión de taller",
                                    commission.commission_amount,
                                    lang=_owner.language_preference or "es",
                                ),
                            )
            except Exception:
                pass

            return CoreResponse(
                success=True,
                status_code=200,
                message="Comisión marcada como errónea. Puede volver a registrar el pago.",
            )

        @self._router.patch("/commissions/workshop/{workshop_id}/register-payment-all", response_model=CoreResponse)
        async def register_all_commissions_payment(
            workshop_id: UUID,
            body: RegisterCommissionPaymentRequest,
            _: CurrentUser = Depends(require_superadmin),
        ):
            """Superadmin registers a single payment for ALL pending commissions of a workshop."""
            async with get_session() as session:
                stmt = select(WorkshopCommissionModel).where(
                    WorkshopCommissionModel.workshop_id == workshop_id,
                    WorkshopCommissionModel.status == "PENDING",
                )
                r = await session.execute(stmt)
                commissions = r.scalars().all()
                if not commissions:
                    raise HTTPException(status_code=400, detail="No hay comisiones pendientes para este taller")

                total_amount = 0.0
                for comm in commissions:
                    comm.status = "PENDING_VERIFICATION"
                    comm.payment_method = body.payment_method
                    comm.reference_number = body.reference_number
                    if body.rate is not None:
                        comm.rate = body.rate
                    if body.rate_date:
                        try:
                            comm.rate_date = datetime.fromisoformat(body.rate_date)
                        except ValueError:
                            pass
                    total_amount += comm.commission_amount
                    session.add(comm)
                await session.commit()

            return CoreResponse(
                success=True,
                status_code=200,
                message=f"Pago registrado para {len(commissions)} comisiones. Total: ${total_amount:.2f}. Pendiente de verificación.",
            )

        @self._router.patch("/commissions/workshop/{workshop_id}/mark-paid-all", response_model=CoreResponse)
        async def mark_all_commissions_paid(
            workshop_id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            """Superadmin marks ALL pending verification commissions of a workshop as paid."""
            async with get_session() as session:
                stmt = select(WorkshopCommissionModel).where(
                    WorkshopCommissionModel.workshop_id == workshop_id,
                    WorkshopCommissionModel.status == "PENDING_VERIFICATION",
                )
                r = await session.execute(stmt)
                commissions = r.scalars().all()
                if not commissions:
                    raise HTTPException(status_code=400, detail="No hay comisiones pendientes de verificación para este taller")

                total_amount = 0.0
                for comm in commissions:
                    comm.status = "PAID"
                    comm.paid_at = datetime.now(timezone.utc)
                    total_amount += comm.commission_amount
                    session.add(comm)

                # Auto-restore workshop since all commissions are now paid
                ws_model = await session.get(WorkshopModel, workshop_id)
                if ws_model:
                    ws_model.commission_suspended = 0
                    ws_model.is_suspended = 0
                    ws_model.commission_warned_at = None
                    session.add(ws_model)

                await session.commit()

            # Notify workshop owner
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_verified_user
                from src.config.models import User as _U, Workshop as _W
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _ws = (await _s.execute(_sel(_W).where(_W.id == workshop_id))).scalars().first()
                    if _ws:
                        _owner = (await _s.execute(_sel(_U).where(_U.id == _ws.owner_id))).scalars().first()
                        if _owner:
                            await send_email(
                                _owner.email,
                                "Comisiones verificadas - AutoTech",
                                payment_verified_user(
                                    f"{_owner.first_name} {_owner.last_name}",
                                    f"Comisiones de taller ({len(commissions)} comisiones)",
                                    total_amount,
                                    lang=_owner.language_preference or "es",
                                ),
                            )
            except Exception:
                pass

            return CoreResponse(
                success=True,
                status_code=200,
                message=f"{len(commissions)} comisiones verificadas. Total: ${total_amount:.2f}",
            )

        @self._router.patch("/commissions/workshop/{workshop_id}/mark-erroneous-all", response_model=CoreResponse)
        async def mark_all_commissions_erroneous(
            workshop_id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            """Superadmin rejects ALL pending verification commissions of a workshop back to PENDING."""
            async with get_session() as session:
                stmt = select(WorkshopCommissionModel).where(
                    WorkshopCommissionModel.workshop_id == workshop_id,
                    WorkshopCommissionModel.status == "PENDING_VERIFICATION",
                )
                r = await session.execute(stmt)
                commissions = r.scalars().all()
                if not commissions:
                    raise HTTPException(status_code=400, detail="No hay comisiones pendientes de verificación para este taller")

                total_amount = 0.0
                for comm in commissions:
                    comm.status = "PENDING"
                    comm.payment_method = None
                    comm.reference_number = None
                    comm.paid_at = None
                    total_amount += comm.commission_amount
                    session.add(comm)
                await session.commit()

            # Notify workshop owner
            try:
                from src.utils.email import send_email
                from src.utils.email_templates import payment_rejected_user
                from src.config.models import User as _U, Workshop as _W
                from sqlalchemy import select as _sel
                async with get_session() as _s:
                    _ws = (await _s.execute(_sel(_W).where(_W.id == workshop_id))).scalars().first()
                    if _ws:
                        _owner = (await _s.execute(_sel(_U).where(_U.id == _ws.owner_id))).scalars().first()
                        if _owner:
                            await send_email(
                                _owner.email,
                                "Comisiones rechazadas - AutoTech",
                                payment_rejected_user(
                                    f"{_owner.first_name} {_owner.last_name}",
                                    f"Comisiones de taller ({len(commissions)} comisiones)",
                                    total_amount,
                                    lang=_owner.language_preference or "es",
                                ),
                            )
            except Exception as e:
                import logging
                logging.error(f"Error sending commission rejection email: {e}")

            return CoreResponse(
                success=True,
                status_code=200,
                message=f"{len(commissions)} comisiones rechazadas. Total: ${total_amount:.2f}",
            )

        # --- Admin Payment Methods (Superadmin) ---

        class AdminPaymentMethodDTO(BaseModel):
            id: str
            label: str
            method_type: str
            bank_name: str | None = None
            account_number: str | None = None
            holder_name: str | None = None
            holder_ci: str | None = None
            phone: str | None = None
            email: str | None = None
            is_active: bool
            created_at: str

        class AdminPaymentMethodListDTO(BaseModel):
            methods: list[AdminPaymentMethodDTO]

        class CreatePaymentMethodRequest(BaseModel):
            label: str
            method_type: str
            bank_name: str | None = None
            account_number: str | None = None
            holder_name: str | None = None
            holder_ci: str | None = None
            phone: str | None = None
            email: str | None = None

        @self._router.get("/payment-methods", response_model=CoreResponse[AdminPaymentMethodListDTO])
        async def list_payment_methods(
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import AdminPaymentMethod as APModel
            async with get_session() as session:
                stmt = select(APModel).order_by(APModel.created_at.desc())
                r = await session.execute(stmt)
                methods = r.scalars().all()

            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminPaymentMethodListDTO(
                    methods=[
                        AdminPaymentMethodDTO(
                            id=str(m.id),
                            label=m.label,
                            method_type=m.method_type,
                            bank_name=m.bank_name,
                            account_number=m.account_number,
                            holder_name=m.holder_name,
                            holder_ci=m.holder_ci,
                            phone=m.phone,
                            email=m.email,
                            is_active=bool(m.is_active),
                            created_at=m.created_at.isoformat() if m.created_at else "",
                        )
                        for m in methods
                    ],
                ),
            )

        @self._router.post("/payment-methods", response_model=CoreResponse[AdminPaymentMethodDTO])
        async def create_payment_method(
            body: CreatePaymentMethodRequest,
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import AdminPaymentMethod as APModel
            async with get_session() as session:
                method = APModel(
                    label=body.label,
                    method_type=body.method_type,
                    bank_name=body.bank_name,
                    account_number=body.account_number,
                    holder_name=body.holder_name,
                    holder_ci=body.holder_ci,
                    phone=body.phone,
                    email=body.email,
                )
                session.add(method)
                await session.flush()
                await session.commit()

            return CoreResponse(
                success=True,
                status_code=201,
                message="Método de pago creado",
                content=AdminPaymentMethodDTO(
                    id=str(method.id),
                    label=method.label,
                    method_type=method.method_type,
                    bank_name=method.bank_name,
                    account_number=method.account_number,
                    holder_name=method.holder_name,
                    holder_ci=method.holder_ci,
                    phone=method.phone,
                    email=method.email,
                    is_active=True,
                    created_at=method.created_at.isoformat() if method.created_at else "",
                ),
            )

        @self._router.patch("/payment-methods/{id}/toggle", response_model=CoreResponse)
        async def toggle_payment_method(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import AdminPaymentMethod as APModel
            async with get_session() as session:
                method = await session.get(APModel, id)
                if not method:
                    raise HTTPException(status_code=404, detail="Método de pago no encontrado")
                method.is_active = 0 if method.is_active else 1
                await session.commit()

            return CoreResponse(
                success=True,
                status_code=200,
                message="Método de pago actualizado",
            )

        @self._router.delete("/payment-methods/{id}", response_model=CoreResponse)
        async def delete_payment_method(
            id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            from src.config.models import AdminPaymentMethod as APModel
            async with get_session() as session:
                method = await session.get(APModel, id)
                if not method:
                    raise HTTPException(status_code=404, detail="Método de pago no encontrado")
                await session.delete(method)
                await session.commit()

            return CoreResponse(
                success=True,
                status_code=200,
                message="Método de pago eliminado",
            )

        # --- Superadmin: Create User ---

        class SuperadminCreateUserRequest(BaseModel):
            email: str
            password: str
            first_name: str
            last_name: str
            ci: str
            phone: str
            role: str  # CLIENT, WORKSHOP_OWNER, ADMIN
            credit_level: int = 1
            parts_credit_limit: float = 150
            service_credit_limit: float = 50

        @self._router.post("/users", response_model=CoreResponse)
        async def superadmin_create_user(
            body: SuperadminCreateUserRequest,
            _: CurrentUser = Depends(require_superadmin),
        ):
            import bcrypt
            from src.config.models import User as UserModel, UserRole as UserRoleModel
            from src.utils.venezuelan_validators import validate_ci, validate_phone

            if body.role == "SUPERADMIN":
                raise HTTPException(status_code=403, detail="No se puede crear un SUPERADMIN")

            if body.role not in ("CLIENT", "WORKSHOP_OWNER", "ADMIN"):
                raise HTTPException(status_code=400, detail="Rol inválido")

            try:
                validate_ci(body.ci)
            except ValueError:
                raise HTTPException(status_code=400, detail="CI inválido")

            try:
                validate_phone(body.phone)
            except ValueError:
                raise HTTPException(status_code=400, detail="Teléfono inválido")

            async with get_session() as session:
                existing = await session.execute(
                    select(UserModel).where(UserModel.email == body.email)
                )
                if existing.scalars().first():
                    raise HTTPException(status_code=400, detail="El correo ya está registrado")

                pw_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
                user = UserModel(
                    email=body.email,
                    password_hash=pw_hash,
                    first_name=body.first_name,
                    last_name=body.last_name,
                    ci=body.ci,
                    phone=body.phone,
                    credit_level=body.credit_level,
                    parts_credit_limit=body.parts_credit_limit,
                    service_credit_limit=body.service_credit_limit,
                )
                session.add(user)
                await session.flush()
                session.add(UserRoleModel(user_id=user.id, role_id=ROLE_NAME_TO_UUID[body.role]))
                await session.commit()

            return CoreResponse(
                success=True,
                status_code=201,
                message=f"Usuario {body.role} creado exitosamente",
            )

        # --- Support Messages ---

        class CreateSupportMessageRequest(BaseModel):
            subject: str
            message: str
            type: str = "OTHER"  # REPORT, QUESTION, SUGGESTION, COMPLAINT, OTHER
            related_order_id: str | None = None

        class SupportMessageDTO(BaseModel):
            id: str
            user_id: str
            user_name: str
            user_email: str
            subject: str
            message: str
            type: str
            related_order_id: str | None
            related_order_type: str | None = None
            status: str
            created_at: str
            read_at: str | None
            resolved_at: str | None
            admin_note: str | None

        class SupportMessageListDTO(BaseModel):
            messages: list[SupportMessageDTO]
            total: int

        @self._router.post("/support/messages", response_model=CoreResponse)
        async def create_support_message(
            body: CreateSupportMessageRequest,
            current_user: CurrentUser = Depends(get_current_user),
        ):
            """Any authenticated user can send a support message."""
            async with get_session() as session:
                msg = SupportMessageModel(
                    user_id=current_user.id,
                    subject=body.subject,
                    message=body.message,
                    type=body.type,
                    related_order_id=UUID(body.related_order_id) if body.related_order_id else None,
                    status="PENDING",
                )
                session.add(msg)
                await session.commit()
            return CoreResponse(
                success=True,
                status_code=201,
                message="Mensaje enviado correctamente",
            )

        @self._router.get("/admin/support/messages", response_model=CoreResponse[SupportMessageListDTO])
        async def list_support_messages(
            status: str | None = Query(default=None),
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                stmt = select(SupportMessageModel, UserModel).join(
                    UserModel, UserModel.id == SupportMessageModel.user_id
                ).order_by(SupportMessageModel.created_at.desc())
                if status:
                    stmt = stmt.where(SupportMessageModel.status == status)
                r = await session.execute(stmt)
                results = r.unique().all()
                # Pre-fetch order types for all related_order_ids in one pass
                order_ids = [msg.related_order_id for msg, _ in results if msg.related_order_id]
                order_type_map: dict[UUID, str] = {}
                if order_ids:
                    parts_ids = {r[0] for r in (await session.execute(select(OrderModel.id).where(OrderModel.id.in_(order_ids)))).all()}
                    service_ids = {r[0] for r in (await session.execute(select(ServiceOrderModel.id).where(ServiceOrderModel.id.in_(order_ids)))).all()}
                    for oid in order_ids:
                        if oid in parts_ids:
                            order_type_map[oid] = "PARTS"
                        elif oid in service_ids:
                            order_type_map[oid] = "SERVICE"
                msgs = []
                for msg, user in results:
                    msgs.append(SupportMessageDTO(
                        id=str(msg.id),
                        user_id=str(msg.user_id),
                        user_name=f"{user.first_name} {user.last_name}",
                        user_email=user.email,
                        subject=msg.subject,
                        message=msg.message,
                        type=msg.type,
                        related_order_id=str(msg.related_order_id) if msg.related_order_id else None,
                        related_order_type=order_type_map.get(msg.related_order_id) if msg.related_order_id else None,
                        status=msg.status,
                        created_at=msg.created_at.isoformat() if msg.created_at else "",
                        read_at=msg.read_at.isoformat() if msg.read_at else None,
                        resolved_at=msg.resolved_at.isoformat() if msg.resolved_at else None,
                        admin_note=msg.admin_note,
                    ))
                return CoreResponse(
                    success=True,
                    status_code=200,
                    content=SupportMessageListDTO(messages=msgs, total=len(msgs)),
                )

        @self._router.get("/admin/support/messages/{id}", response_model=CoreResponse[SupportMessageDTO])
        async def get_support_message(
            id: UUID,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                msg = await session.get(SupportMessageModel, id)
                if not msg:
                    raise HTTPException(status_code=404, detail="Mensaje no encontrado")
                user = await session.get(UserModel, msg.user_id)
                related_order_type = None
                if msg.related_order_id:
                    if await session.get(OrderModel, msg.related_order_id):
                        related_order_type = "PARTS"
                    elif await session.get(ServiceOrderModel, msg.related_order_id):
                        related_order_type = "SERVICE"
                return CoreResponse(
                    success=True,
                    status_code=200,
                    content=SupportMessageDTO(
                        id=str(msg.id),
                        user_id=str(msg.user_id),
                        user_name=f"{user.first_name} {user.last_name}" if user else "N/A",
                        user_email=user.email if user else "N/A",
                        subject=msg.subject,
                        message=msg.message,
                        type=msg.type,
                        related_order_id=str(msg.related_order_id) if msg.related_order_id else None,
                        related_order_type=related_order_type,
                        status=msg.status,
                        created_at=msg.created_at.isoformat() if msg.created_at else "",
                        read_at=msg.read_at.isoformat() if msg.read_at else None,
                        resolved_at=msg.resolved_at.isoformat() if msg.resolved_at else None,
                        admin_note=msg.admin_note,
                    ),
                )

        class ResolveSupportMessageRequest(BaseModel):
            admin_note: str | None = None

        @self._router.patch("/admin/support/messages/{id}/resolve", response_model=CoreResponse)
        async def resolve_support_message(
            id: UUID,
            body: ResolveSupportMessageRequest,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                msg = await session.get(SupportMessageModel, id)
                if not msg:
                    raise HTTPException(status_code=404, detail="Mensaje no encontrado")
                msg.status = "RESOLVED"
                msg.resolved_at = datetime.now(timezone.utc)
                if body.admin_note:
                    msg.admin_note = body.admin_note
                session.add(msg)
                await session.commit()
                user = await session.get(UserModel, msg.user_id)
            # Send email notification to user in their language
            if user:
                try:
                    from src.utils.email import send_email
                    from src.utils.email_templates import support_resolved
                    lang = getattr(user, "language_preference", "es") or "es"
                    await send_email(
                        user.email,
                        "Soporte resuelto - AutoTech" if lang == "es" else "Support resolved - AutoTech",
                        support_resolved(
                            user_name=f"{user.first_name} {user.last_name}",
                            subject=msg.subject,
                            admin_note=body.admin_note,
                            lang=lang,
                        ),
                    )
                except Exception:
                    pass
            return CoreResponse(success=True, status_code=200, message="Mensaje resuelto")

        @self._router.patch("/admin/support/messages/{id}/reject", response_model=CoreResponse)
        async def reject_support_message(
            id: UUID,
            body: ResolveSupportMessageRequest,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                msg = await session.get(SupportMessageModel, id)
                if not msg:
                    raise HTTPException(status_code=404, detail="Mensaje no encontrado")
                msg.status = "REJECTED"
                msg.resolved_at = datetime.now(timezone.utc)
                if body.admin_note:
                    msg.admin_note = body.admin_note
                session.add(msg)
                await session.commit()
                user = await session.get(UserModel, msg.user_id)
            # Send email notification to user in their language
            if user:
                try:
                    from src.utils.email import send_email
                    from src.utils.email_templates import support_rejected
                    lang = getattr(user, "language_preference", "es") or "es"
                    await send_email(
                        user.email,
                        "Soporte rechazado - AutoTech" if lang == "es" else "Support rejected - AutoTech",
                        support_rejected(
                            user_name=f"{user.first_name} {user.last_name}",
                            subject=msg.subject,
                            admin_note=body.admin_note,
                            lang=lang,
                        ),
                    )
                except Exception:
                    pass
            return CoreResponse(success=True, status_code=200, message="Mensaje rechazado")

        # --- Late Fees Users Summary (Superadmin) ---

        class LateFeeUserSummaryDTO(BaseModel):
            user_id: str
            user_name: str
            user_email: str
            late_fees_count: int
            total_late_fees_amount: float
            oldest_late_fee_days: int
            total_active_debt: float
            active_orders_count: int

        class LateFeeUsersSummaryDTO(BaseModel):
            users: list[LateFeeUserSummaryDTO]

        @self._router.get("/admin/late-fees/users-summary", response_model=CoreResponse[LateFeeUsersSummaryDTO])
        async def late_fees_users_summary(
            _: CurrentUser = Depends(require_superadmin),
        ):
            """Group late fees by user, calculate days since oldest, sum active orders."""
            async with get_session() as session:
                # Group late fees by user
                stmt = (
                    select(
                        LateFeeModel.user_id,
                        func.count(LateFeeModel.id).label("count"),
                        func.sum(LateFeeModel.amount).label("total_amount"),
                        func.min(LateFeeModel.created_at).label("oldest_created"),
                    )
                    .where(LateFeeModel.status == "PENDING")
                    .group_by(LateFeeModel.user_id)
                )
                r = await session.execute(stmt)
                fee_groups = r.all()

                summaries = []
                now = datetime.now(timezone.utc)
                for uid, count, total_amount, oldest_created in fee_groups:
                    user = await session.get(UserModel, uid)
                    if not user:
                        continue
                    days_old = (now - oldest_created).days if oldest_created else 0

                    # Count active orders (parts + service) and their pending amounts
                    parts_stmt = (
                        select(func.coalesce(func.sum(InstallmentModel.amount), 0))
                        .join(OrderModel, InstallmentModel.order_id == OrderModel.id)
                        .where(
                            OrderModel.user_id == uid,
                            InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                        )
                    )
                    parts_pending = float((await session.execute(parts_stmt)).scalar() or 0)

                    svc_stmt = (
                        select(func.coalesce(func.sum(ServiceOrderInstallmentModel.amount), 0))
                        .join(ServiceOrderModel, ServiceOrderInstallmentModel.service_order_id == ServiceOrderModel.id)
                        .where(
                            ServiceOrderModel.user_id == uid,
                            ServiceOrderInstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                        )
                    )
                    svc_pending = float((await session.execute(svc_stmt)).scalar() or 0)

                    active_orders = int(
                        (await session.execute(
                            select(func.count(OrderModel.id)).where(
                                OrderModel.user_id == uid,
                                OrderModel.status.in_(["PENDING_VERIFICATION", "PENDING_CONFIRMATION", "PAID", "FINANCED", "SHIPPED", "RECEIVED"]),
                            )
                        )).scalar() or 0
                    ) + int(
                        (await session.execute(
                            select(func.count(ServiceOrderModel.id)).where(
                                ServiceOrderModel.user_id == uid,
                                ServiceOrderModel.status.in_(["ACCEPTED", "IN_PROGRESS", "COMPLETED"]),
                            )
                        )).scalar() or 0
                    )

                    summaries.append(LateFeeUserSummaryDTO(
                        user_id=str(uid),
                        user_name=f"{user.first_name} {user.last_name}",
                        user_email=user.email,
                        late_fees_count=int(count),
                        total_late_fees_amount=float(total_amount or 0),
                        oldest_late_fee_days=days_old,
                        total_active_debt=parts_pending + svc_pending,
                        active_orders_count=active_orders,
                    ))

                return CoreResponse(
                    success=True,
                    status_code=200,
                    content=LateFeeUsersSummaryDTO(users=summaries),
                )

        class UserOrderSummaryDTO(BaseModel):
            type: str  # PARTS or SERVICE
            id: str
            short_id: str
            workshop_name: str
            total_amount: float
            pending_amount: float
            status: str
            created_at: str

        class UserOrdersSummaryDTO(BaseModel):
            orders: list[UserOrderSummaryDTO]

        @self._router.get("/admin/late-fees/users/{user_id}/orders", response_model=CoreResponse[UserOrdersSummaryDTO])
        async def user_orders_summary(
            user_id: UUID,
            _: CurrentUser = Depends(require_superadmin),
        ):
            """Get active orders (parts + service) for a user with pending amounts."""
            async with get_session() as session:
                orders = []

                # Parts orders
                parts_stmt = (
                    select(OrderModel, WorkshopModel)
                    .join(WorkshopModel, WorkshopModel.id == OrderModel.workshop_id)
                    .where(
                        OrderModel.user_id == user_id,
                        OrderModel.status.in_(["PENDING_VERIFICATION", "PENDING_CONFIRMATION", "PAID", "FINANCED", "SHIPPED", "RECEIVED"]),
                    )
                    .order_by(OrderModel.created_at.desc())
                )
                r = await session.execute(parts_stmt)
                for order, ws in r.all():
                    pending_stmt = select(func.coalesce(func.sum(InstallmentModel.amount), 0)).where(
                        InstallmentModel.order_id == order.id,
                        InstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    )
                    pending = float((await session.execute(pending_stmt)).scalar() or 0)
                    orders.append(UserOrderSummaryDTO(
                        type="PARTS",
                        id=str(order.id),
                        short_id=f"#{str(order.id)[:8]}",
                        workshop_name=ws.name,
                        total_amount=float(order.total_amount or 0),
                        pending_amount=pending,
                        status=order.status,
                        created_at=order.created_at.isoformat() if order.created_at else "",
                    ))

                # Service orders
                svc_stmt = (
                    select(ServiceOrderModel, WorkshopModel)
                    .join(WorkshopModel, WorkshopModel.id == ServiceOrderModel.workshop_id)
                    .where(
                        ServiceOrderModel.user_id == user_id,
                        ServiceOrderModel.status.in_(["ACCEPTED", "IN_PROGRESS", "COMPLETED"]),
                    )
                    .order_by(ServiceOrderModel.created_at.desc())
                )
                r = await session.execute(svc_stmt)
                for so, ws in r.all():
                    pending_stmt = select(func.coalesce(func.sum(ServiceOrderInstallmentModel.amount), 0)).where(
                        ServiceOrderInstallmentModel.service_order_id == so.id,
                        ServiceOrderInstallmentModel.status.in_(["PENDING", "PENDING_VERIFICATION", "OVERDUE"]),
                    )
                    pending = float((await session.execute(pending_stmt)).scalar() or 0)
                    total = float(so.final_price or so.base_price or 0)
                    orders.append(UserOrderSummaryDTO(
                        type="SERVICE",
                        id=str(so.id),
                        short_id=f"#{str(so.id)[:8]}",
                        workshop_name=ws.name,
                        total_amount=total,
                        pending_amount=pending,
                        status=so.status,
                        created_at=so.created_at.isoformat() if so.created_at else "",
                    ))

                return CoreResponse(
                    success=True,
                    status_code=200,
                    content=UserOrdersSummaryDTO(orders=orders),
                )
