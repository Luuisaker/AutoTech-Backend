from dataclasses import dataclass
from uuid import UUID
from src.core.domain.entity import Entity


@dataclass
class Cart(Entity):
    user_id: UUID


@dataclass
class CartItem(Entity):
    cart_id: UUID
    part_id: UUID
    quantity: int = 1
