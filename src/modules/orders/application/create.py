from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CheckoutItemInput(BaseModel):
    cart_item_id: str
    down_payment_percentage: float | None = Field(default=None, ge=0, le=100)


class WorkshopCheckoutInput(BaseModel):
    workshop_id: UUID
    delivery_method: str = "PICKUP"
    delivery_address: str | None = None
    reference_number: str | None = Field(default=None, max_length=100)
    payment_method_id: UUID | None = None
    items: list[CheckoutItemInput]


class CheckoutRequest(BaseModel):
    vehicle_id: UUID | None = None
    mileage: int = 0
    workshops: list[WorkshopCheckoutInput]


class OrderItemDTO(BaseModel):
    id: UUID
    part_id: UUID
    workshop_id: UUID
    part_name: str
    quantity: int
    unit_price: float

    model_config = ConfigDict(from_attributes=True)


class OrderRatingInfo(BaseModel):
    client_rating: int | None = None
    client_rated: bool = False
    workshop_rating: int | None = None
    workshop_rated: bool = False


class OrderDTO(BaseModel):
    id: UUID
    vehicle_id: UUID
    total_amount: float
    down_payment: float
    financed_amount: float
    installment_count: int
    status: str
    delivery_method: str
    delivery_address: str | None
    delivery_fee: float
    reference_number: str | None
    tracking_number: str | None
    shipping_notes: str | None
    shipped_at: datetime | None
    workshop_name: str | None
    workshop_id: str | None
    items: list[OrderItemDTO]
    closed_by_client: bool = False
    closed_by_workshop: bool = False
    created_at: datetime
    ratings: OrderRatingInfo = Field(default_factory=OrderRatingInfo)

    model_config = ConfigDict(from_attributes=True)


class OrderListDTO(BaseModel):
    orders: list[OrderDTO]


class InstallmentDTO(BaseModel):
    id: UUID
    order_id: UUID
    amount: float
    due_date: datetime
    payment_method: str | None = None
    reference_number: str | None = None
    status: str
    paid_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class InstallmentListDTO(BaseModel):
    installments: list[InstallmentDTO]


class PayInstallmentRequest(BaseModel):
    payment_method: str = Field(..., pattern="BANK_TRANSFER|MOBILE_PAYMENT|CASH|OTHER")
    reference_number: str = Field(..., min_length=1, max_length=100)


class MarkInstallmentPaidRequest(BaseModel):
    reference_number: str | None = Field(default=None, max_length=100)


class ConfirmPaymentRequest(BaseModel):
    reference_number: str = Field(..., min_length=1, max_length=100)


class WorkshopOrderDTO(BaseModel):
    id: UUID
    user_id: UUID
    vehicle_id: UUID
    mileage: int
    total_amount: float
    status: str
    delivery_method: str
    delivery_address: str | None
    delivery_fee: float
    reference_number: str | None
    confirmed_at: datetime | None
    closed_by_client: bool = False
    closed_by_workshop: bool = False
    items: list[OrderItemDTO]
    created_at: datetime
    ratings: OrderRatingInfo = Field(default_factory=OrderRatingInfo)

    model_config = ConfigDict(from_attributes=True)


class WorkshopOrderListDTO(BaseModel):
    orders: list[WorkshopOrderDTO]


class RateOrderRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class MarkShippedRequest(BaseModel):
    tracking_number: str = Field(..., max_length=100)
    shipping_notes: str | None = Field(default=None, max_length=500)
