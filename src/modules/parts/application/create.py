from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from src.modules.parts.domain.types import PartCategory


class CreatePartRequest(BaseModel):
    workshop_id: UUID = Field(...)
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    price: float = Field(..., gt=0)
    stock: int = Field(..., ge=0)
    condition: str = Field(default="NEW", pattern="NEW|USED")
    category: str | None = Field(
        default=None,
        pattern="|".join(c.value for c in PartCategory),
    )
    allows_installments: int = Field(default=0, ge=0, le=1)
    installment_min_percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class UpdatePartRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)
    description: str | None = Field(default=None, max_length=2000)
    price: float | None = Field(default=None, gt=0)
    stock: int | None = Field(default=None, ge=0)
    condition: str | None = Field(default=None, pattern="NEW|USED")
    category: str | None = Field(
        default=None,
        pattern="|".join(c.value for c in PartCategory),
    )
    allows_installments: int | None = Field(default=None, ge=0, le=1)
    installment_min_percentage: float | None = Field(default=None, ge=0.0, le=100.0)
    is_active: int | None = Field(default=None, ge=0, le=1)


class PartDTO(BaseModel):
    id: UUID
    workshop_id: UUID
    name: str
    description: str | None
    price: float
    stock: int
    condition: str
    category: str | None
    allows_installments: int
    installment_min_percentage: float
    is_active: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartListDTO(BaseModel):
    parts: list[PartDTO]


class PartCategoryListDTO(BaseModel):
    categories: list[str]


class PurchasePartRequest(BaseModel):
    part_id: UUID | None = None
    vehicle_id: UUID
    quantity: int = Field(..., ge=1)
    mileage: int = Field(..., ge=0)
    installment_count: int = Field(default=0, ge=0, le=24)


class PartPurchaseDTO(BaseModel):
    id: UUID
    part_id: UUID
    user_id: UUID
    workshop_id: UUID
    vehicle_id: UUID
    mileage: int
    quantity: int
    unit_price: float
    total_amount: float
    down_payment: float
    financed_amount: float
    installment_count: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PartPurchaseListDTO(BaseModel):
    purchases: list[PartPurchaseDTO]


class PartPaymentDTO(BaseModel):
    id: UUID
    purchase_id: UUID
    amount: float
    due_date: datetime
    payment_method: str
    reference_number: str | None
    status: str
    paid_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class PartPaymentListDTO(BaseModel):
    payments: list[PartPaymentDTO]


class RecordPaymentRequest(BaseModel):
    payment_method: str = Field(..., pattern="BANK_TRANSFER|MOBILE_PAYMENT|CASH|OTHER")
    reference_number: str | None = Field(default=None, max_length=100)
