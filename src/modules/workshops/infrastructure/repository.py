from typing import Sequence, cast
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.elements import ColumnElement

from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import Workshop as WorkshopModel
from src.config.models import (
    WorkshopBankAccount as WorkshopBankAccountModel,
)
from src.config.models import (
    WorkshopMobilePayment as WorkshopMobilePaymentModel,
)
from src.config.models import (
    WorkshopPaymentMethod as WorkshopPaymentMethodModel,
)


class WorkshopRepository(GenericSQLRepository[WorkshopModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkshopModel)

    async def get_by_rif(self, rif: str) -> WorkshopModel | None:
        condition = cast(ColumnElement[bool], WorkshopModel.rif == rif)
        stmt = select(WorkshopModel).where(
            condition, WorkshopModel.deleted_at.is_(None)
        )
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def list_by_owner(self, owner_id: str) -> Sequence[WorkshopModel]:
        condition = cast(ColumnElement[bool], WorkshopModel.owner_id == owner_id)
        stmt = select(WorkshopModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def search(
        self,
        query: str | None = None,
        certified_only: bool = False,
        owner_id: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> Sequence[WorkshopModel]:
        if owner_id:
            return await self.list_by_owner(owner_id)

        stmt = select(WorkshopModel)
        where_clauses: list = [
            cast(ColumnElement[bool], WorkshopModel.is_suspended == 0),
            cast(ColumnElement[bool], WorkshopModel.deleted_at.is_(None)),
        ]

        if query:
            like_pattern = f"%{query}%"
            where_clauses.append(
                cast(ColumnElement[bool], WorkshopModel.name.ilike(like_pattern))
            )

        if certified_only:
            where_clauses.append(
                cast(ColumnElement[bool], WorkshopModel.is_certified == 1)
            )

        if where_clauses:
            stmt = stmt.where(*where_clauses)

        stmt = stmt.limit(limit).offset(offset)
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def list_pending_verifications(self) -> Sequence[WorkshopModel]:
        stmt = (
            select(WorkshopModel)
            .where(
                cast(ColumnElement[bool], WorkshopModel.is_certified == 0),
                cast(
                    ColumnElement[bool],
                    WorkshopModel.verification_document_url.isnot(None),
                ),
                cast(ColumnElement[bool], WorkshopModel.deleted_at.is_(None)),
            )
            .options(selectinload(WorkshopModel.owner))
            .order_by(WorkshopModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()


class WorkshopBankAccountRepository(GenericSQLRepository[WorkshopBankAccountModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkshopBankAccountModel)

    async def list_by_workshop(
        self, workshop_id: str
    ) -> Sequence[WorkshopBankAccountModel]:
        condition = cast(
            ColumnElement[bool], WorkshopBankAccountModel.workshop_id == workshop_id
        )
        stmt = select(WorkshopBankAccountModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()


class WorkshopMobilePaymentRepository(GenericSQLRepository[WorkshopMobilePaymentModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkshopMobilePaymentModel)

    async def list_by_workshop(
        self, workshop_id: str
    ) -> Sequence[WorkshopMobilePaymentModel]:
        condition = cast(
            ColumnElement[bool],
            WorkshopMobilePaymentModel.workshop_id == workshop_id,
        )
        stmt = select(WorkshopMobilePaymentModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()


class WorkshopPaymentMethodRepository(GenericSQLRepository[WorkshopPaymentMethodModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, WorkshopPaymentMethodModel)

    async def list_by_workshop(
        self, workshop_id: str
    ) -> Sequence[WorkshopPaymentMethodModel]:
        condition = cast(
            ColumnElement[bool],
            WorkshopPaymentMethodModel.workshop_id == workshop_id,
        )
        stmt = select(WorkshopPaymentMethodModel).where(condition)
        r = await self._session.execute(stmt)
        return r.scalars().all()
