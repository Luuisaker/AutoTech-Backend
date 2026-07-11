from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from src.core.application.base_request import Request
from src.modules.vehicles.domain.types import VehicleType


class CreateVehicleRequest(Request):
    vehicle_type: str = Field(
        ...,
        pattern="|".join(v.value for v in VehicleType),
    )
    brand: str = Field(..., min_length=1, max_length=64)
    model: str = Field(..., min_length=1, max_length=64)
    year: int = Field(..., ge=1900, le=2100)
    license_plate: str = Field(..., min_length=4, max_length=15)
    vin: str | None = Field(default=None, max_length=17)


class UpdateVehicleRequest(Request):
    vehicle_type: str | None = Field(
        default=None,
        pattern="|".join(v.value for v in VehicleType),
    )
    brand: str | None = Field(default=None, min_length=1, max_length=64)
    model: str | None = Field(default=None, min_length=1, max_length=64)
    year: int | None = Field(default=None, ge=1900, le=2100)


class VehicleListDTO(BaseModel):
    vehicles: list["VehicleDTO"]


class VehicleTypeListDTO(BaseModel):
    types: list[str]


class VehicleDTO(BaseModel):
    id: UUID
    owner_id: UUID
    vehicle_type: str
    brand: str
    model: str
    year: int
    license_plate: str
    vin: str
    photo_url: str | None = None
    is_active: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
