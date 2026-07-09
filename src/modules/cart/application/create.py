from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class AddToCartRequest(BaseModel):
    part_id: UUID
    quantity: int = Field(default=1, ge=1)


class UpdateCartItemRequest(BaseModel):
    quantity: int = Field(..., ge=1)


class CartItemDTO(BaseModel):
    id: UUID
    cart_id: UUID
    part_id: UUID
    quantity: int

    model_config = ConfigDict(from_attributes=True)


class CartItemDetailDTO(BaseModel):
    id: UUID
    part_id: UUID
    part_name: str
    part_price: float
    workshop_id: UUID
    workshop_name: str
    quantity: int
    subtotal: float
    allows_installments: bool = False
    installment_min_percentage: float = 0

    model_config = ConfigDict(from_attributes=True)


class CartDTO(BaseModel):
    id: UUID | None = None
    items: list[CartItemDetailDTO]
    total: float


class WorkshopGroupDTO(BaseModel):
    workshop_id: UUID
    workshop_name: str
    items: list[CartItemDetailDTO]
    subtotal: float


class WorkshopBreakdownDTO(BaseModel):
    groups: list[WorkshopGroupDTO]
    total: float
