from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import Depends, APIRouter, Response, Query, HTTPException
from sqlalchemy import select, func, case
from sqlalchemy.orm import selectinload
from src.core.infrastructure.router import BaseRouter
from src.core.application.base_response import Response as CoreResponse
from src.config.database import get_session
from src.config.models import User as UserModel
from src.config.models import Workshop as WorkshopModel
from src.config.models import Part as PartModel
from src.config.models import Vehicle as VehicleModel
from src.config.models import UserRole as UserRoleModel
from src.config.models import (
    WorkshopService as WorkshopServiceModel,
)
from src.config.models import Order as OrderModel
from src.config.models import OrderItem as OrderItemModel
from src.config.models import Installment as InstallmentModel
from src.config.models import ServiceOrder as ServiceOrderModel
from src.modules.users.infrastructure.auth import CurrentUser
from src.modules.users.infrastructure.permissions import require_admin
from src.modules.users.infrastructure.repository import UserRepository
from src.modules.users.infrastructure.mapper import UserMapper
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


class AdminUpdateWorkshopRequest(BaseModel):
    name: str | None = None
    address: str | None = None
    rif: str | None = None
    is_certified: int | None = None
    is_suspended: int | None = None


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
            async with get_session() as session:
                user_count = (
                    await session.execute(select(func.count(UserModel.id)))
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

                # Monthly revenue (last 30 days)
                thirty_days_ago = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                ) - timedelta(days=30)
                revenue_result = await session.execute(
                    select(func.sum(OrderModel.total_amount)).where(
                        OrderModel.deleted_at.is_(None),
                        OrderModel.created_at >= thirty_days_ago,
                    )
                )
                monthly_revenue = float(revenue_result.scalar() or 0.0)

                # Total financed (sum of unpaid installments)
                financed_result = await session.execute(
                    select(func.coalesce(func.sum(InstallmentModel.amount), 0)).where(
                        InstallmentModel.status != "PAID",
                        InstallmentModel.deleted_at.is_(None),
                    )
                )
                total_financed = float(financed_result.scalar() or 0.0)

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
                ),
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
                # ── Orders (parts) ──
                order_stmt = (
                    select(
                        WorkshopModel.owner_id,
                        UserModel.first_name,
                        UserModel.last_name,
                        WorkshopModel.id,
                        WorkshopModel.name,
                        func.count(OrderModel.id.distinct()).label("order_count"),
                        func.coalesce(func.sum(OrderModel.total_amount), 0).label("order_revenue"),
                        func.coalesce(
                            func.sum(
case(
    (InstallmentModel.status == "PAID", InstallmentModel.amount),
    else_=0,
)
                            ),
                            0,
                        ).label("order_paid"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (InstallmentModel.status == "PENDING", InstallmentModel.amount),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("order_pending"),
                    )
                    .select_from(OrderModel)
                    .join(OrderItemModel, OrderItemModel.order_id == OrderModel.id)
                    .join(WorkshopModel, WorkshopModel.id == OrderItemModel.workshop_id)
                    .join(UserModel, UserModel.id == WorkshopModel.owner_id)
                    .outerjoin(InstallmentModel, InstallmentModel.order_id == OrderModel.id)
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
                                case(
                                    (
                                        ServiceOrderModel.status.in_(["COMPLETED", "DELIVERED"]),
                                        func.coalesce(ServiceOrderModel.final_price, ServiceOrderModel.base_price),
                                    ),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("svc_paid"),
                        func.coalesce(
                            func.sum(
                                case(
                                    (
                                        ~ServiceOrderModel.status.in_(["COMPLETED", "DELIVERED", "CANCELLED"]),
                                        func.coalesce(ServiceOrderModel.final_price, ServiceOrderModel.base_price),
                                    ),
                                    else_=0,
                                )
                            ),
                            0,
                        ).label("svc_pending"),
                    )
                    .select_from(ServiceOrderModel)
                    .join(WorkshopModel, WorkshopModel.id == ServiceOrderModel.workshop_id)
                    .join(UserModel, UserModel.id == WorkshopModel.owner_id)
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
            _: CurrentUser = Depends(require_admin),
        ):
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
                # Filter out ADMIN users
                users = [
                    u
                    for u in all_users
                    if not any(role.role == "ADMIN" for role in u.roles)
                ]

            _mapper = UserMapper()
            return CoreResponse(
                success=True,
                status_code=200,
                content=AdminUserListDTO(
                    users=[UserDTO.model_validate(_mapper.to_entity(u)) for u in users]
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
                content=UserDTO.model_validate(UserMapper().to_entity(user)),
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
                content=UserDTO.model_validate(UserMapper().to_entity(user)),
            )

        @self._router.delete("/users/{id}", response_model=CoreResponse)
        async def delete_user(
            id: UUID,
            response: Response,
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                repo = UserRepository(session)
                user = await repo.get(str(id))
                if not user:
                    raise HTTPException(status_code=404, detail="Usuario no encontrado")
                user.deleted_at = datetime.now(timezone.utc)
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
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                workshop = await session.get(WorkshopModel, id)
                if not workshop:
                    raise HTTPException(status_code=404, detail="Taller no encontrado")

                now = datetime.now(timezone.utc)
                workshop.deleted_at = now

                # Soft delete parts belonging to this workshop
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

        @self._router.get("/vehicles", response_model=CoreResponse[VehicleListDTO])
        async def list_vehicles(
            offset: int = Query(default=0, ge=0),
            limit: int = Query(default=100, ge=1, le=200),
            search: str | None = Query(default=None),
            _: CurrentUser = Depends(require_admin),
        ):
            async with get_session() as session:
                stmt = (
                    select(VehicleModel)
                    .where(VehicleModel.deleted_at.is_(None))
                )
                if search:
                    pattern = f"%{search}%"
                    stmt = stmt.where(
                        VehicleModel.vehicle_type.ilike(pattern) |
                        VehicleModel.license_plate.ilike(pattern) |
                        VehicleModel.model.ilike(pattern) |
                        VehicleModel.brand.ilike(pattern)
                    )
                stmt = stmt.offset(offset).limit(limit).order_by(VehicleModel.created_at.desc())
                r = await session.execute(stmt)
                vehicles = r.scalars().all()

            return CoreResponse(
                success=True,
                status_code=200,
                content=VehicleListDTO(
                    vehicles=[VehicleDTO.model_validate(v) for v in vehicles]
                ),
            )

        # --- Orders ---

        class AdminOrderDTO(BaseModel):
            id: str
            user_id: str
            buyer_name: str
            buyer_ci: str | None
            vehicle_id: str
            workshop_name: str
            mileage: int
            total_amount: float
            status: str
            payment_status: str
            installment_count: int
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
                if status:
                    stmt = stmt.where(OrderModel.status == status)
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

                return CoreResponse(
                    success=True,
                    status_code=200,
                    content=AdminOrderListDTO(orders=[
                        AdminOrderDTO(
                            id=str(o.id),
                            user_id=str(o.user_id),
                            buyer_name=f"{fn} {ln}".strip(),
                            buyer_ci=ci,
                            vehicle_id=str(o.vehicle_id),
                            workshop_name=wn,
                            mileage=o.mileage,
                            total_amount=o.total_amount,
                            status="CLOSED" if o.status in ("RECEIVED", "CANCELLED") else "PENDING",
                            payment_status=o.status,
                            installment_count=len(o.installments) if o.installments else 0,
                            created_at=o.created_at.isoformat() if o.created_at else "",
                        )
                        for o, fn, ln, ci, wn in orders_data
                    ]),
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
                    )
                    .join(WorkshopModel, ServiceOrderModel.workshop_id == WorkshopModel.id)
                    .join(VehicleModel, ServiceOrderModel.vehicle_id == VehicleModel.id)
                )
                
                # Apply filters
                if search:
                    stmt = stmt.where(
                        (ServiceOrderModel.id.ilike(f"%{search}%")) |
                        (WorkshopModel.name.ilike(f"%{search}%")) |
                        (VehicleModel.brand.ilike(f"%{search}%")) |
                        (VehicleModel.model.ilike(f"%{search}%"))
                    )
                
                if status:
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
            _: CurrentUser = Depends(require_admin),
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
                await session.commit()

                return CoreResponse(
                    success=True,
                    status_code=200,
                    message="Orden eliminada exitosamente",
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
