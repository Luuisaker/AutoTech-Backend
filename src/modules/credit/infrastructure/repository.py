from typing import Sequence
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.core.infrastructure.sql_repository import GenericSQLRepository
from src.config.models import CreditLevel as CreditLevelModel, CreditHistory as CreditHistoryModel, CreditLimitReview as CreditLimitReviewModel, LateFee as LateFeeModel


class CreditLevelRepository(GenericSQLRepository[CreditLevelModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CreditLevelModel)

    async def list_all(self) -> Sequence[CreditLevelModel]:
        stmt = select(CreditLevelModel).order_by(CreditLevelModel.level.desc())
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def get_by_level(self, level: int) -> CreditLevelModel | None:
        stmt = select(CreditLevelModel).where(CreditLevelModel.level == level)
        r = await self._session.execute(stmt)
        return r.scalars().first()


class CreditHistoryRepository(GenericSQLRepository[CreditHistoryModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CreditHistoryModel)

    async def list_by_user(self, user_id: str, limit: int = 50) -> Sequence[CreditHistoryModel]:
        stmt = (
            select(CreditHistoryModel)
            .where(CreditHistoryModel.user_id == UUID(user_id) if isinstance(user_id, str) else user_id)
            .order_by(CreditHistoryModel.created_at.desc())
            .limit(limit)
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def add_entry(
        self,
        user_id: UUID,
        type: str,
        amount: float = 0.0,
        parts_line_used: float = 0.0,
        service_line_used: float = 0.0,
        description: str = "",
        reference_id: UUID | None = None,
    ) -> CreditHistoryModel:
        entry = CreditHistoryModel(
            user_id=user_id,
            type=type,
            amount=amount,
            parts_line_used=parts_line_used,
            service_line_used=service_line_used,
            description=description,
            reference_id=reference_id,
        )
        self._session.add(entry)
        await self._session.flush()
        return entry


class CreditLimitReviewRepository(GenericSQLRepository[CreditLimitReviewModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, CreditLimitReviewModel)

    async def get_last_by_user(self, user_id: str) -> CreditLimitReviewModel | None:
        stmt = (
            select(CreditLimitReviewModel)
            .where(CreditLimitReviewModel.user_id == user_id)
            .order_by(CreditLimitReviewModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def list_pending(self) -> Sequence[CreditLimitReviewModel]:
        stmt = (
            select(CreditLimitReviewModel)
            .where(CreditLimitReviewModel.status == "PENDING")
            .order_by(CreditLimitReviewModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def list_by_user(self, user_id: str) -> Sequence[CreditLimitReviewModel]:
        stmt = (
            select(CreditLimitReviewModel)
            .where(CreditLimitReviewModel.user_id == user_id)
            .order_by(CreditLimitReviewModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()


class LateFeeRepository(GenericSQLRepository[LateFeeModel]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, LateFeeModel)

    async def find_open_by_installment(
        self, installment_id: UUID, installment_type: str
    ) -> LateFeeModel | None:
        stmt = (
            select(LateFeeModel)
            .where(
                LateFeeModel.installment_id == installment_id,
                LateFeeModel.installment_type == installment_type,
                LateFeeModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
            )
        )
        r = await self._session.execute(stmt)
        return r.scalars().first()

    async def list_open_by_user(self, user_id: UUID) -> Sequence[LateFeeModel]:
        stmt = (
            select(LateFeeModel)
            .where(
                LateFeeModel.user_id == user_id,
                LateFeeModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
            )
            .order_by(LateFeeModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def list_by_user(self, user_id: UUID) -> Sequence[LateFeeModel]:
        stmt = (
            select(LateFeeModel)
            .where(
                LateFeeModel.user_id == user_id,
                LateFeeModel.status.in_(["PENDING", "PENDING_VERIFICATION"]),
            )
            .order_by(LateFeeModel.created_at.desc())
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()

    async def find_penalty_history_by_installment(
        self, installment_id: UUID
    ) -> Sequence[CreditHistoryModel]:
        """Find PENALTY credit_history entries for a given installment."""
        stmt = (
            select(CreditHistoryModel)
            .where(
                CreditHistoryModel.reference_id == installment_id,
                CreditHistoryModel.type == "PENALTY",
            )
        )
        r = await self._session.execute(stmt)
        return r.scalars().all()
