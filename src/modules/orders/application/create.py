from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CheckoutRequest(BaseModel):
    vehicle_id: UUID
    mileage: int = Field(..., ge=0)
    installment_count: int = Field(default=0, ge=0, le=24)


class OrderItemDTO(BaseModel):
    id: UUID
    part_id: UUID
    part_name: str
    quantity: int
    unit_price: float

    model_config = ConfigDict(from_attributes=True)


class OrderDTO(BaseModel):
    id: UUID
    vehicle_id: UUID
    total_amount: float
    down_payment: float
    financed_amount: float
    installment_count: int
    status: str
    items: list[OrderItemDTO]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderListDTO(BaseModel):
    orders: list[OrderDTO]


class InstallmentDTO(BaseModel):
    id: UUID
    amount: float
    due_date: datetime
    status: str
    paid_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class InstallmentListDTO(BaseModel):
    installments: list[InstallmentDTO]


class PayInstallmentRequest(BaseModel):
    payment_method: str = Field(..., pattern="BANK_TRANSFER|MOBILE_PAYMENT|CASH|OTHER")
    reference_number: str | None = Field(default=None, max_length=100)
