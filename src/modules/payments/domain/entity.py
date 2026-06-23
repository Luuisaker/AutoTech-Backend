from dataclasses import dataclass
from uuid import UUID
from src.core.domain.entity import Entity


@dataclass
class UserPaymentAccount(Entity):
    user_id: UUID
    account_type: str
    bank_name: str
    holder_document: str
    account_number: str | None = None
    account_holder: str | None = None
    phone_number: str | None = None
    is_active: int = 1
