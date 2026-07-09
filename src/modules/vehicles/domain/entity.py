from dataclasses import dataclass
from uuid import UUID
from src.core.domain.entity import Entity


@dataclass
class Vehicle(Entity):
    owner_id: UUID
    vehicle_type: str
    brand: str
    model: str
    year: int
    license_plate: str
    vin: str
    photo_url: str | None = None
    is_active: int = 1
