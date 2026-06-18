from dataclasses import dataclass
from uuid import UUID
from src.core.domain.entity import Entity


@dataclass
class Workshop(Entity):
    owner_id: UUID
    name: str
    rif: str
    address: str
    latitude: float | None = None
    longitude: float | None = None
    is_certified: int = 0
    average_rating: float = 0.0
    verification_document_url: str | None = None
