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
    photo_url: str | None = None


@dataclass
class WorkshopBankAccount(Entity):
    workshop_id: UUID
    account_number: str
    holder_ci: str
    bank_name: str
    is_active: int = 1


@dataclass
class WorkshopMobilePayment(Entity):
    workshop_id: UUID
    phone_number: str
    bank_name: str
    holder_ci: str
    is_active: int = 1
