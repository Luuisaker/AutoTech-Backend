from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import WorkshopService as ServiceModel
from src.config.models import Workshop as WorkshopModel


class ServiceRepository(GenericSQLRepository[ServiceModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, ServiceModel)

    async def delete(self, record: ServiceModel) -> None:
        await self._session.delete(record)
        await self._session.flush()

    async def list_by_workshop(self, workshop_id: str) -> Sequence[ServiceModel]:
        condition = cast(ColumnElement[bool], ServiceModel.workshop_id == workshop_id)
        stmt = select(ServiceModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def search(
        self,
        query: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        certified_only: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[ServiceModel]:
        stmt = select(ServiceModel).join(
            WorkshopModel, ServiceModel.workshop_id == WorkshopModel.id
        )
        where_clauses: list = []

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
