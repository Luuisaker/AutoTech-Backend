from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ServiceOrderRatingInfo(BaseModel):
    client_rating: int | None = None
    client_rated: bool = False
    client_review: str | None = None
    workshop_rating: int | None = None
    workshop_rated: bool = False
    workshop_review: str | None = None


class ServiceOrderPaymentDTO(BaseModel):
    id: UUID
    amount: float
    payment_method: str
    reference_number: str | None = None
    status: str
    paid_at: datetime | None = None
    rate: float | None = None
    rate_date: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceOrderInstallmentDTO(BaseModel):
    id: UUID
    amount: float
    due_date: datetime
    payment_method: str = "OTHER"
    reference_number: str | None = None
    status: str
    paid_at: datetime | None = None
    rate: float | None = None
    rate_date: datetime | None = None
    created_at: datetime
    late_fee_status: str | None = None
    late_fee_amount: float | None = None

    model_config = ConfigDict(from_attributes=True)


class CreateServiceRequest(BaseModel):
    workshop_id: UUID
    service_name: str = Field(..., min_length=1, max_length=128)
    service_type: str | None = None
    standard_price_min: float = Field(..., ge=0)
    standard_price_max: float = Field(..., ge=0)
    vehicle_type: str | None = "ALL"
    revision_cost_min: float | None = Field(default=None, ge=0)
    revision_cost_max: float | None = Field(default=None, ge=0)


class UpdateServiceRequest(BaseModel):
    service_name: str | None = Field(default=None, min_length=1, max_length=128)
    service_type: str | None = None
    standard_price_min: float | None = Field(default=None, ge=0)
    standard_price_max: float | None = Field(default=None, ge=0)
    vehicle_type: str | None = None
    revision_cost_min: float | None = None
    revision_cost_max: float | None = None


class ServiceDTO(BaseModel):
    id: UUID
    workshop_id: UUID
    service_name: str
    service_type: str | None
    standard_price_min: float
    standard_price_max: float
    vehicle_type: str | None
    revision_cost_min: float | None = None
    revision_cost_max: float | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceWithWorkshopDTO(ServiceDTO):
    workshop_name: str | None = None
    workshop_address: str | None = None
    workshop_photo_url: str | None = None
    workshop_certified: bool | None = None
    workshop_rating: float | None = None


class ServiceWithWorkshopListDTO(BaseModel):
    services: list[ServiceWithWorkshopDTO]


class ServiceListDTO(BaseModel):
    services: list[ServiceDTO]


class CreateServiceOrderRequest(BaseModel):
    workshop_id: UUID
    service_id: UUID
    vehicle_id: UUID
    base_price: float | None = Field(default=None, ge=0)
    notes: str | None = None


class SetQuoteRequest(BaseModel):
    final_price: float = Field(..., ge=0)
    notes: str | None = None


class SetRevisionRequest(BaseModel):
    revision_cost: float = Field(..., ge=0)


class UpdateServiceOrderStatusRequest(BaseModel):
    status: str = Field(..., pattern="IN_PROGRESS|COMPLETED|CANCELLED")


class AddExtraChargeRequest(BaseModel):
    extra_charge: float = Field(..., ge=0)
    extra_charge_note: str | None = None


class MarkServiceShippedRequest(BaseModel):
    tracking_number: str = Field(..., max_length=100)
    shipping_notes: str = Field(..., max_length=500)


class PayServiceOrderRequest(BaseModel):
    payment_method: str = Field(..., pattern="BANK_TRANSFER|MOBILE_PAYMENT|CASH|OTHER")
    reference_number: str | None = None
    rate: float | None = None
    rate_date: datetime | None = None
    paid_at: datetime | None = None


class FinanceServiceOrderRequest(BaseModel):
    down_payment_pct: float = Field(..., ge=0, le=100)
    payment_method: str = Field(..., pattern="BANK_TRANSFER|MOBILE_PAYMENT|CASH|OTHER")
    reference_number: str | None = None
    rate: float | None = None
    rate_date: datetime | None = None


class AcceptQuoteRequest(BaseModel):
    is_financed: bool = False
    down_payment_pct: float | None = Field(default=None, ge=0, le=100)
    payment_method: str | None = None
    reference_number: str | None = None
    rate: float | None = None
    rate_date: datetime | None = None


class PayServiceInstallmentRequest(BaseModel):
    payment_method: str = Field(..., pattern="BANK_TRANSFER|MOBILE_PAYMENT|CASH|OTHER")
    reference_number: str | None = None
    rate: float | None = None
    rate_date: datetime | None = None
    paid_at: datetime | None = None


class MarkServiceInstallmentPaidRequest(BaseModel):
    paid_at: datetime | None = None


class RateServiceOrderRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class ServiceOrderDTO(BaseModel):
    id: UUID
    user_id: UUID
    workshop_id: UUID
    service_id: UUID
    vehicle_id: UUID
    service_name: str
    workshop_name: str | None
    workshop_rif: str | None
    workshop_address: str | None
    vehicle_brand: str
    vehicle_model: str
    vehicle_license_plate: str
    user_first_name: str
    user_last_name: str
    user_ci: str
    user_email: str
    owner_first_name: str | None = None
    owner_last_name: str | None = None
    owner_ci: str | None = None
    owner_email: str | None = None
    user_client_rating: float | None = None
    user_client_rating_count: int | None = None
    status: str
    base_price: float
    final_price: float | None
    extra_charge: float
    extra_charge_note: str | None
    extra_charge_status: str
    price_min: float | None
    price_max: float | None
    notes: str | None
    delivery_method: str = "PICKUP"
    tracking_number: str | None = None
    shipping_notes: str | None = None
    shipped_at: datetime | None = None
    closed_by_client: bool = False
    closed_by_workshop: bool = False
    revision: float | None = None
    is_paid: bool = False
    is_financed: bool = False
    down_payment_pct: float | None = None
    created_at: datetime
    completed_at: datetime | None
    delivered_at: datetime | None
    payment_status: str | None = None
    ratings: ServiceOrderRatingInfo = Field(default_factory=ServiceOrderRatingInfo)
    payments: list[ServiceOrderPaymentDTO] = Field(default_factory=list)
    installments: list[ServiceOrderInstallmentDTO] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class ServiceOrderListDTO(BaseModel):
    service_orders: list[ServiceOrderDTO]


class AdminServiceOrderDetailDTO(ServiceOrderDTO):
    pass
