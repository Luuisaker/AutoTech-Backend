from dataclasses import dataclass
from uuid import UUID
from datetime import datetime
from src.core.domain.entity import Entity


@dataclass
class Order(Entity):
    user_id: UUID
    vehicle_id: UUID
    mileage: int = 0
    total_amount: float = 0.0
    status: str = "PENDING"


@dataclass
class OrderItem(Entity):
    order_id: UUID
    part_id: UUID
    quantity: int = 1
    unit_price: float = 0.0


@dataclass
class Installment(Entity):
    order_id: UUID
    amount: float = 0.0
    due_date: datetime | None = None
    status: str = "PENDING"
    paid_at: datetime | None = None


@dataclass
class Transaction(Entity):
    order_id: UUID
    installment_id: UUID | None = None
    payer_user_id: UUID | None = None
    receiver_workshop_id: UUID | None = None
    amount: float = 0.0
    payment_method: str = "OTHER"
    status: str = "PENDING"
