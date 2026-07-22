from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime
from src.core.application.base_request import Request
from src.modules.users.domain.types import UserRole
from src.utils.venezuelan_validators import (
    validate_ci as _validate_ci,
    validate_phone as _validate_phone,
)


class CreateUserRequest(Request):
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: str = Field(..., min_length=2, max_length=64)
    last_name: str = Field(..., min_length=2, max_length=64)
    ci: str = Field(..., min_length=6, max_length=15)
    phone: str = Field(..., min_length=6, max_length=15)
    role: UserRole = UserRole.CLIENT

    @field_validator("ci")
    @classmethod
    def check_ci(cls, v: str) -> str:
        return _validate_ci(v)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str) -> str:
        return _validate_phone(v)


class UserDTO(BaseModel):
    id: UUID
    email: str
    roles: list[str]
    first_name: str
    last_name: str
    ci: str
    phone: str | None
    photo_url: str | None = None
    is_suspended: int = 0
    client_average_rating: float = 0.0
    client_rating_count: int = 0
    credit_level: int = 1
    parts_credit_limit: float = 150.0
    service_credit_limit: float = 50.0
    parts_available: float = 150.0
    service_available: float = 50.0
    total_parts_debt: float = 0.0
    total_service_debt: float = 0.0
    is_2fa_enabled: int = 0
    language_preference: str = "es"
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
