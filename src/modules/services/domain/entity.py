from dataclasses import dataclass
from uuid import UUID
from src.core.domain.entity import Entity


@dataclass
class Service(Entity):
    workshop_id: UUID
    service_name: str
    service_type: str | None = None
    standard_price_min: float = 0.0
    standard_price_max: float = 0.0
    revision_cost_min: float | None = None
    revision_cost_max: float | None = None
    vehicle_type: str | None = "ALL"
