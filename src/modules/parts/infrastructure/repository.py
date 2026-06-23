from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import Part as PartModel
from src.config.models import PartPurchase as PartPurchaseModel
from src.config.models import PartPayment as PartPaymentModel
from src.config.models import VehicleHistoryLog as VehicleHistoryLogModel


class PartRepository(GenericSQLRepository[PartModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PartModel)

    async def list_by_workshop(
        self, workshop_id: str, offset: int = 0, limit: int = 100
    ) -> Sequence[PartModel]:
        condition = cast(ColumnElement[bool], PartModel.workshop_id == workshop_id)
        stmt = select(PartModel).where(condition).limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def search(
        self,
        query: str | None = None,
        category: str | None = None,
        condition: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        certified_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[PartModel]:
        from src.config.models import Workshop as WorkshopModel

        stmt = select(PartModel).join(
            WorkshopModel, PartModel.workshop_id == WorkshopModel.id
        )
        where_clauses: list = [cast(ColumnElement[bool], PartModel.is_active == 1)]

        if certified_only:
            where_clauses.append(
                cast(ColumnElement[bool], WorkshopModel.is_certified == 1)
            )

        if query:
            like_pattern = f"%{query}%"
            where_clauses.append(
                cast(ColumnElement[bool], PartModel.name.ilike(like_pattern))
            )

        if category:
            where_clauses.append(
                cast(ColumnElement[bool], PartModel.category == category)
            )

        if condition:
            where_clauses.append(
                cast(ColumnElement[bool], PartModel.condition == condition)
            )

        if min_price is not None:
            where_clauses.append(
                cast(ColumnElement[bool], PartModel.price >= min_price)
            )

        if max_price is not None:
            where_clauses.append(
                cast(ColumnElement[bool], PartModel.price <= max_price)
            )

        stmt = stmt.where(*where_clauses).limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.scalars().all()


class PartPurchaseRepository(GenericSQLRepository[PartPurchaseModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PartPurchaseModel)

    async def list_by_user(
        self, user_id: str, offset: int = 0, limit: int = 100
    ) -> Sequence[PartPurchaseModel]:
        condition = cast(ColumnElement[bool], PartPurchaseModel.user_id == user_id)
        stmt = select(PartPurchaseModel).where(condition).limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def list_by_workshop(
        self, workshop_id: str, offset: int = 0, limit: int = 100
    ) -> Sequence[PartPurchaseModel]:
        condition = cast(
            ColumnElement[bool], PartPurchaseModel.workshop_id == workshop_id
        )
        stmt = select(PartPurchaseModel).where(condition).limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.scalars().all()


class PartPaymentRepository(GenericSQLRepository[PartPaymentModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, PartPaymentModel)

    async def list_by_purchase(self, purchase_id: str) -> Sequence[PartPaymentModel]:
        condition = cast(
            ColumnElement[bool], PartPaymentModel.purchase_id == purchase_id
        )
        stmt = select(PartPaymentModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()


class VehicleHistoryLogRepository(GenericSQLRepository[VehicleHistoryLogModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, VehicleHistoryLogModel)
