from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class ServiceOrderRatingInfo(BaseModel):
    client_rating: int | None = None
    client_rated: bool = False
    workshop_rating: int | None = None
    workshop_rated: bool = False


class CreateServiceRequest(BaseModel):
    workshop_id: UUID
    service_name: str = Field(..., min_length=1, max_length=128)
    service_type: str | None = None
    standard_price_min: float = Field(..., ge=0)
    standard_price_max: float = Field(..., ge=0)
    vehicle_type: str | None = "ALL"


class UpdateServiceRequest(BaseModel):
    service_name: str | None = Field(default=None, min_length=1, max_length=128)
    service_type: str | None = None
    standard_price_min: float | None = Field(default=None, ge=0)
    standard_price_max: float | None = Field(default=None, ge=0)
    vehicle_type: str | None = None


class ServiceDTO(BaseModel):
    id: UUID
    workshop_id: UUID
    service_name: str
    service_type: str | None
    standard_price_min: float
    standard_price_max: float
    vehicle_type: str | None
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


class UpdateServiceOrderStatusRequest(BaseModel):
    status: str = Field(..., pattern="IN_PROGRESS|COMPLETED|CANCELLED")


class AddExtraChargeRequest(BaseModel):
    extra_charge: float = Field(..., ge=0)
    extra_charge_note: str | None = None


class MarkServiceShippedRequest(BaseModel):
    tracking_number: str = Field(..., max_length=100)
    shipping_notes: str | None = Field(default=None, max_length=500)


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
    vehicle_brand: str
    vehicle_model: str
    vehicle_license_plate: str
    user_first_name: str
    user_last_name: str
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
    created_at: datetime
    completed_at: datetime | None
    delivered_at: datetime | None
    ratings: ServiceOrderRatingInfo = Field(default_factory=ServiceOrderRatingInfo)

    model_config = ConfigDict(from_attributes=True)


class ServiceOrderListDTO(BaseModel):
    service_orders: list[ServiceOrderDTO]
