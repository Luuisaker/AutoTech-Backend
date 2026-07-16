from dataclasses import dataclass, field
from uuid import UUID, uuid4
from datetime import datetime
from src.core.domain.entity import Entity


@dataclass(kw_only=True)
class CreditLevel(Entity):
    level: int = 1
    points_required: float = 0.0
    credit_multiplier: float = 1.0
    min_down_payment_pct: float = 0.0
    base_parts_limit: float = 150.0


@dataclass(kw_only=True)
class CreditHistory(Entity):
    user_id: UUID
    type: str  # PURCHASE, PAYMENT, PENALTY, LEVEL_CHANGE, ADMIN_ADJUST
    amount: float = 0.0
    parts_line_used: float = 0.0
    service_line_used: float = 0.0
    description: str = ""
    reference_id: UUID | None = None
