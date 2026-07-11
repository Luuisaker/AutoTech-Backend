from typing import Sequence, cast
import uuid
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import WorkshopService as ServiceModel
from src.config.models import Workshop as WorkshopModel
from src.config.models import ServiceOrder as ServiceOrderModel
from src.config.models import ServiceOrderPayment as ServiceOrderPaymentModel


class ServiceRepository(GenericSQLRepository[ServiceModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ServiceModel)

    async def list_by_workshop(self, workshop_id: str) -> Sequence[ServiceModel]:
        condition = cast(ColumnElement[bool], ServiceModel.workshop_id == workshop_id)
        stmt = select(ServiceModel).where(condition, ServiceModel.deleted_at.is_(None))
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def search(
        self,
        query: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        certified_only: bool = False,
        service_type: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ServiceModel]:
        stmt = select(ServiceModel).join(
            WorkshopModel, ServiceModel.workshop_id == WorkshopModel.id
        )
        where_clauses: list = [cast(ColumnElement[bool], ServiceModel.deleted_at.is_(None)), cast(ColumnElement[bool], WorkshopModel.is_suspended == 0)]

        if certified_only:
            where_clauses.append(
                cast(ColumnElement[bool], WorkshopModel.is_certified == 1)
            )

        if query:
            like_pattern = f"%{query}%"
            where_clauses.append(
                cast(
                    ColumnElement[bool],
                    ServiceModel.service_name.ilike(like_pattern),
                )
            )

        if service_type:
            where_clauses.append(
                cast(
                    ColumnElement[bool],
                    ServiceModel.service_type == service_type,
                )
            )

        if min_price is not None:
            where_clauses.append(
                cast(
                    ColumnElement[bool],
                    ServiceModel.standard_price_max >= min_price,
                )
            )

        if max_price is not None:
            where_clauses.append(
                cast(
                    ColumnElement[bool],
                    ServiceModel.standard_price_min <= max_price,
                )
            )

        if where_clauses:
            stmt = stmt.where(*where_clauses)

        stmt = stmt.limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def search_with_workshop(
        self,
        query: str | None = None,
        service_type: str | None = None,
        certified_only: bool = False,
        workshop_id: uuid.UUID | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ServiceModel]:
        stmt = (
            select(
                ServiceModel,
                WorkshopModel.name.label("workshop_name"),
                WorkshopModel.address.label("workshop_address"),
                WorkshopModel.photo_url.label("workshop_photo_url"),
                WorkshopModel.is_certified.label("workshop_certified"),
            )
            .join(WorkshopModel, ServiceModel.workshop_id == WorkshopModel.id)
        )
        where_clauses: list = [cast(ColumnElement[bool], ServiceModel.deleted_at.is_(None)), cast(ColumnElement[bool], WorkshopModel.is_suspended == 0)]

        if certified_only:
            where_clauses.append(
                cast(ColumnElement[bool], WorkshopModel.is_certified == 1)
            )

        if query:
            like_pattern = f"%{query}%"
            where_clauses.append(
                cast(
                    ColumnElement[bool],
                    ServiceModel.service_name.ilike(like_pattern),
                )
            )

        if service_type:
            where_clauses.append(
                cast(
                    ColumnElement[bool],
                    ServiceModel.service_type == service_type,
                )
            )

        if workshop_id:
            where_clauses.append(
                cast(ColumnElement[bool], ServiceModel.workshop_id == workshop_id)
            )

        if where_clauses:
            stmt = stmt.where(*where_clauses)

        stmt = stmt.limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.all()


class ServiceOrderRepository(GenericSQLRepository[ServiceOrderModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ServiceOrderModel)

    async def get_with_relations(self, id_: str) -> ServiceOrderModel | None:
        condition = cast(ColumnElement[bool], ServiceOrderModel.id == id_)
        stmt = (
            select(ServiceOrderModel)
            .options(
                selectinload(ServiceOrderModel.workshop_service),
                selectinload(ServiceOrderModel.workshop),
                selectinload(ServiceOrderModel.vehicle),
                selectinload(ServiceOrderModel.user),
                selectinload(ServiceOrderModel.payments),
            )
            .where(condition)
        )
        r = await self._session.execute(stmt)
        return r.scalars().first()
    async def list_by_user(self, user_id: str) -> Sequence[ServiceOrderModel]:
        condition = cast(ColumnElement[bool], ServiceOrderModel.user_id == user_id)
        stmt = (
            select(ServiceOrderModel)
            .options(
                selectinload(ServiceOrderModel.workshop_service),
                selectinload(ServiceOrderModel.workshop),
                selectinload(ServiceOrderModel.vehicle),
                selectinload(ServiceOrderModel.user),
                selectinload(ServiceOrderModel.payments),
            )
            .where(condition)
            .order_by(ServiceOrderModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()


    async def list_by_workshop(self, workshop_id: str) -> Sequence[ServiceOrderModel]:
        condition = cast(ColumnElement[bool], ServiceOrderModel.workshop_id == workshop_id)
        stmt = (
            select(ServiceOrderModel)
            .options(
                selectinload(ServiceOrderModel.workshop_service),
                selectinload(ServiceOrderModel.workshop),
                selectinload(ServiceOrderModel.vehicle),
                selectinload(ServiceOrderModel.user),
                selectinload(ServiceOrderModel.payments),
            )
            .where(condition)
            .order_by(ServiceOrderModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()


class ServiceOrderPaymentRepository(GenericSQLRepository[ServiceOrderPaymentModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ServiceOrderPaymentModel)

    async def get_by_service_order(self, service_order_id: str) -> Sequence[ServiceOrderPaymentModel]:
        condition = cast(ColumnElement[bool], ServiceOrderPaymentModel.service_order_id == service_order_id)
        stmt = select(ServiceOrderPaymentModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()
