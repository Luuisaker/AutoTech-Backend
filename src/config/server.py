import os
import sys
import asyncio
import logging

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles

from src.config.settings import settings
from src.utils.add_routers import add_routers

from src.modules.users.infrastructure.router import UserRouter
from src.modules.vehicles.infrastructure.router import VehicleRouter
from src.modules.workshops.infrastructure.router import WorkshopRouter
from src.modules.parts.infrastructure.router import PartRouter
from src.modules.services.infrastructure.router import ServiceRouter
from src.modules.payments.infrastructure.router import PaymentRouter
from src.modules.cart.infrastructure.router import CartRouter
from src.modules.orders.infrastructure.router import OrderRouter
from src.modules.admin.infrastructure.router import AdminRouter
from src.modules.credit.infrastructure.router import CreditRouter

logger = logging.getLogger(__name__)

routers = [
    UserRouter(),
    VehicleRouter(),
    WorkshopRouter(),
    PartRouter(),
    ServiceRouter(),
    PaymentRouter(),
    CartRouter(),
    OrderRouter(),
    AdminRouter(),
    CreditRouter(),
]


class App:
    _penalty_task = None
    _commission_task = None

    def __init__(self) -> None:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

        self.server = FastAPI(
            title="AutoTech API",
            description="Backend API for AutoTech",
            version="1.0.0",
            lifespan=self._lifespan,
        )

        self._setup_middlewares()
        self._setup_base_routes()
        self._setup_static_files()

        add_routers(self.server, routers)

    @asynccontextmanager
    async def _lifespan(self, app):
        App._penalty_task = asyncio.create_task(self._run_daily_penalties())
        App._commission_task = asyncio.create_task(self._run_daily_commission_checks())
        yield
        if App._penalty_task:
            App._penalty_task.cancel()
            try:
                await App._penalty_task
            except asyncio.CancelledError:
                pass
        if App._commission_task:
            App._commission_task.cancel()
            try:
                await App._commission_task
            except asyncio.CancelledError:
                pass

    def _setup_middlewares(self) -> None:
        self.server.add_middleware(GZipMiddleware, minimum_size=500)

        origins = [
            "http://localhost:8080",
            "http://127.0.0.1:8080",
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
        if settings.FRONTEND_URL and settings.FRONTEND_URL not in origins:
            origins.append(settings.FRONTEND_URL)
        self.server.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    def _setup_base_routes(self) -> None:
        @self.server.get("/health", tags=["Status"])
        async def health_check():
            return {"status": "ok", "message": "AutoTech API is running"}

        @self.server.post("/cron/apply-penalties", tags=["Cron"])
        async def apply_penalties(api_key: str = ""):
            if api_key != settings.CRON_API_KEY:
                from fastapi import HTTPException
                raise HTTPException(status_code=403, detail="Invalid API key")
            from src.modules.credit.infrastructure.service import CreditService
            from src.config.database import get_session
            from sqlalchemy import select
            from src.config.models import User as UserModel
            svc = CreditService()
            async with get_session() as session:
                stmt = select(UserModel).where(UserModel.deleted_at.is_(None))
                r = await session.execute(stmt)
                users = r.scalars().all()
            results = []
            for u in users:
                result = await svc.apply_late_penalties(u.id)
                results.append({"user_id": str(u.id), "message": result.message})
            return {"processed": len(results), "results": results}

    async def _run_daily_penalties(self, interval_hours: int = 24) -> None:
        while True:
            try:
                await asyncio.sleep(interval_hours * 3600)
                await self._apply_all_penalties()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in penalty scheduler: {e}")

    async def _apply_all_penalties(self) -> None:
        try:
            from src.modules.credit.infrastructure.service import CreditService
            from src.config.database import get_session
            from sqlalchemy import select, and_
            from src.config.models import User as UserModel
            from src.config.models import Installment as InstModel, Order as OrdModel
            from src.config.models import ServiceOrderInstallment as SOIModel, ServiceOrder as SOModel
            from datetime import datetime, timezone, timedelta
            svc = CreditService()
            async with get_session() as session:
                stmt = select(UserModel).where(UserModel.deleted_at.is_(None))
                r = await session.execute(stmt)
                users = r.scalars().all()
            count = 0
            for u in users:
                result = await svc.apply_late_penalties(u.id)
                if result.success:
                    count += 1
            logger.info(f"Penalty scheduler: applied penalties to {count}/{len(users)} users")

            # Send "due in 3 days" notifications
            await self._send_due_soon_notifications()
        except Exception as e:
            logger.error(f"Failed to apply daily penalties: {e}")

    async def _send_due_soon_notifications(self) -> None:
        try:
            from src.config.database import get_session
            from sqlalchemy import select, and_
            from src.config.models import User as UserModel, Installment as InstModel, Order as OrdModel
            from src.config.models import ServiceOrderInstallment as SOIModel, ServiceOrder as SOModel
            from src.utils.email import send_email
            from src.utils.email_templates import installment_due_soon
            from datetime import datetime, timezone, timedelta

            now = datetime.now(timezone.utc)
            in_3_days = now + timedelta(days=3)

            async with get_session() as session:
                # Parts installments due in 3 days
                parts_stmt = (
                    select(InstModel, OrdModel, UserModel)
                    .join(OrdModel, InstModel.order_id == OrdModel.id)
                    .join(UserModel, UserModel.id == OrdModel.user_id)
                    .where(
                        InstModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                        InstModel.deleted_at.is_(None),
                        InstModel.due_date >= now,
                        InstModel.due_date <= in_3_days,
                    )
                )
                r = await session.execute(parts_stmt)
                for inst, order, user in r.all():
                    try:
                        await send_email(
                            user.email,
                            "Vencimiento próximo - AutoTech",
                            installment_due_soon(
                                buyer_name=user.first_name,
                                order_id=str(order.id),
                                installment_number=1,
                                amount=inst.amount,
                                due_date=inst.due_date.strftime("%d/%m/%Y"),
                                lang=user.language_preference or "es",
                            ),
                        )
                    except Exception:
                        pass

                # Service installments due in 3 days
                svc_stmt = (
                    select(SOIModel, SOModel, UserModel)
                    .join(SOModel, SOIModel.service_order_id == SOModel.id)
                    .join(UserModel, UserModel.id == SOModel.user_id)
                    .where(
                        SOIModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
                        SOIModel.due_date >= now,
                        SOIModel.due_date <= in_3_days,
                    )
                )
                r = await session.execute(svc_stmt)
                for inst, order, user in r.all():
                    try:
                        await send_email(
                            user.email,
                            "Vencimiento próximo - AutoTech",
                            installment_due_soon(
                                buyer_name=user.first_name,
                                order_id=str(order.id),
                                installment_number=1,
                                amount=inst.amount,
                                due_date=inst.due_date.strftime("%d/%m/%Y"),
                                lang=user.language_preference or "es",
                            ),
                        )
                    except Exception:
                        pass

            logger.info("Due-soon notifications sent")
        except Exception as e:
            logger.error(f"Failed to send due-soon notifications: {e}")

    async def _run_daily_commission_checks(self, interval_hours: int = 24) -> None:
        """Daily task: warn workshops on day 28/last day, suspend on day 2 of next month."""
        while True:
            try:
                await asyncio.sleep(interval_hours * 3600)
                await self._check_commission_warnings_and_suspensions()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in commission check scheduler: {e}")

    async def _check_commission_warnings_and_suspensions(self) -> None:
        try:
            from src.config.database import get_session
            from sqlalchemy import select, func, and_
            from src.config.models import (
                Workshop as WorkshopModel,
                WorkshopCommission as WCModel,
                User as UserModel,
            )
            from src.utils.email import send_email
            from src.utils.email_templates import commission_due_soon, commission_overdue_suspended
            from datetime import datetime, timezone, timedelta
            import calendar

            now = datetime.now(timezone.utc)
            today = now.date()
            day = today.day
            last_day_of_month = calendar.monthrange(today.year, today.month)[1]

            async with get_session() as session:
                # --- Warning phase: day 28 or last day of month ---
                if day == 28 or day == last_day_of_month:
                    # Find workshops with PENDING commissions in current period that haven't been warned
                    current_month = today.month
                    current_year = today.year
                    deadline_date = today.replace(day=last_day_of_month)
                    deadline_str = deadline_date.strftime("%d/%m/%Y")

                    stmt = (
                        select(
                            WCModel.workshop_id,
                            func.sum(WCModel.commission_amount).label("total_pending"),
                        )
                        .where(
                            WCModel.status == "PENDING",
                            WCModel.period_year == current_year,
                            WCModel.period_month == current_month,
                        )
                        .group_by(WCModel.workshop_id)
                    )
                    r = await session.execute(stmt)
                    workshops_with_pending = r.all()

                    for wid, total_pending in workshops_with_pending:
                        ws = await session.get(WorkshopModel, wid)
                        if not ws or ws.commission_warned_at is not None:
                            continue
                        owner = await session.get(UserModel, ws.owner_id)
                        if not owner:
                            continue
                        try:
                            await send_email(
                                owner.email,
                                "Comisiones por vencer - AutoTech",
                                commission_due_soon(
                                    workshop_name=ws.name,
                                    owner_name=owner.first_name,
                                    total_pending=float(total_pending or 0),
                                    deadline=deadline_str,
                                    lang=owner.language_preference or "es",
                                ),
                            )
                        except Exception:
                            pass
                        ws.commission_warned_at = now
                        session.add(ws)

                    await session.commit()
                    logger.info(f"Commission warnings sent for {len(workshops_with_pending)} workshops")

                # --- Suspension phase: day 2 of next month ---
                elif day == 2:
                    # Previous month/year
                    if today.month == 1:
                        prev_month = 12
                        prev_year = today.year - 1
                    else:
                        prev_month = today.month - 1
                        prev_year = today.year

                    stmt = (
                        select(
                            WCModel.workshop_id,
                            func.sum(WCModel.commission_amount).label("total_pending"),
                        )
                        .where(
                            WCModel.status == "PENDING",
                            WCModel.period_year == prev_year,
                            WCModel.period_month == prev_month,
                        )
                        .group_by(WCModel.workshop_id)
                    )
                    r = await session.execute(stmt)
                    workshops_to_suspend = r.all()

                    for wid, total_pending in workshops_to_suspend:
                        ws = await session.get(WorkshopModel, wid)
                        if not ws:
                            continue
                        ws.commission_suspended = 1
                        ws.is_suspended = 1
                        session.add(ws)

                        owner = await session.get(UserModel, ws.owner_id)
                        if not owner:
                            continue
                        try:
                            await send_email(
                                owner.email,
                                "Taller suspendido por comisiones - AutoTech",
                                commission_overdue_suspended(
                                    workshop_name=ws.name,
                                    owner_name=owner.first_name,
                                    total_pending=float(total_pending or 0),
                                    lang=owner.language_preference or "es",
                                ),
                            )
                        except Exception:
                            pass

                    await session.commit()
                    logger.info(f"Commission suspensions applied to {len(workshops_to_suspend)} workshops")

        except Exception as e:
            logger.error(f"Failed to run commission checks: {e}")

    def _setup_static_files(self) -> None:
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        self.server.mount(
            "/uploads",
            StaticFiles(directory=settings.UPLOAD_DIR),
            name="uploads",
        )
