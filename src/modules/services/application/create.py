from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class CreateServiceRequest(BaseModel):
    workshop_id: UUID
    service_name: str = Field(..., min_length=1, max_length=128)
    standard_price_min: float = Field(..., ge=0)
    standard_price_max: float = Field(..., ge=0)


class UpdateServiceRequest(BaseModel):
    service_name: str | None = Field(default=None, min_length=1, max_length=128)
    standard_price_min: float | None = Field(default=None, ge=0)
    standard_price_max: float | None = Field(default=None, ge=0)


class ServiceDTO(BaseModel):
    id: UUID
    workshop_id: UUID
    service_name: str
    standard_price_min: float
    standard_price_max: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ServiceListDTO(BaseModel):
    services: list[ServiceDTO]
