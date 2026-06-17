from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from src.core.application.base_request import Request


class CreateWorkshopRequest(Request):
    name: str = Field(..., min_length=2, max_length=128)
    rif: str = Field(..., min_length=5, max_length=20)
    address: str = Field(..., min_length=5, max_length=500)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    verification_document_url: str | None = None


class UpdateWorkshopRequest(Request):
    name: str | None = Field(default=None, min_length=2, max_length=128)
    address: str | None = Field(default=None, min_length=5, max_length=500)
    latitude: float | None = None
    longitude: float | None = None
    verification_document_url: str | None = None


class WorkshopDTO(BaseModel):
    id: UUID
    owner_id: UUID
    name: str
    rif: str
    address: str
    latitude: float | None
    longitude: float | None
    is_certified: int
    average_rating: float
    verification_document_url: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WorkshopListDTO(BaseModel):
    workshops: list[WorkshopDTO]
