from typing import Sequence, cast
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import Vehicle as VehicleModel


class VehicleRepository(GenericSQLRepository[VehicleModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, VehicleModel)

    async def get_by_license_plate(self, license_plate: str) -> VehicleModel | None:
        condition = cast(
            ColumnElement[bool], VehicleModel.license_plate == license_plate
        )
        stmt = select(VehicleModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def get_by_vin(self, vin: str) -> VehicleModel | None:
        condition = cast(ColumnElement[bool], VehicleModel.vin == vin)
        stmt = select(VehicleModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def list_by_owner(self, owner_id: str) -> Sequence[VehicleModel]:
        condition = and_(
            cast(ColumnElement[bool], VehicleModel.owner_id == owner_id),
            cast(ColumnElement[bool], VehicleModel.is_active == 1),
        )
        stmt = select(VehicleModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()
