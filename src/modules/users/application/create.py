from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from datetime import datetime
from src.core.application.base_request import Request
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
    email: EmailStr
    role: str
    first_name: str
    last_name: str
    ci: str
    phone: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
