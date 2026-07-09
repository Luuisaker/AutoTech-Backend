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
    delivery_method: str = "PICKUP"
    delivery_address: str | None = None
    delivery_fee: float = 0.0
    reference_number: str | None = None
    confirmed_at: datetime | None = None
    closed_by_client: bool = False
    closed_by_workshop: bool = False


@dataclass
class OrderItem(Entity):
    order_id: UUID
    part_id: UUID
    workshop_id: UUID
    part_name: str | None = None
    quantity: int = 1
    unit_price: float = 0.0


@dataclass
class Installment(Entity):
    order_id: UUID
    amount: float = 0.0
    due_date: datetime | None = None
    payment_method: str = "OTHER"
    reference_number: str | None = None
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
