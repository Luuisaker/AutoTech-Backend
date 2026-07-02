from dataclasses import dataclass
from uuid import UUID
from src.core.domain.entity import Entity


@dataclass
class Part(Entity):
    workshop_id: UUID
    name: str
    description: str | None = None
    price: float = 0.0
    stock: int = 0
    condition: str = "NEW"
    category: str | None = None
    allows_installments: int = 0
    installment_min_percentage: float = 0.0
    photo_url: str | None = None
    is_active: int = 1


@dataclass
class PartPurchase(Entity):
    part_id: UUID
    user_id: UUID
    workshop_id: UUID
    vehicle_id: UUID
    mileage: int = 0
    quantity: int = 1
    unit_price: float = 0.0
    total_amount: float = 0.0
    down_payment: float = 0.0
    financed_amount: float = 0.0
    installment_count: int = 0
    status: str = "PENDING"
