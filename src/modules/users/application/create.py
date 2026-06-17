from uuid import UUID
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from datetime import datetime
from src.core.application.base_request import Request


class CreateUserRequest(Request):
    email: EmailStr
    password: str = Field(..., min_length=6)
    first_name: str = Field(..., min_length=2, max_length=64)
    last_name: str = Field(..., min_length=2, max_length=64)
    ci: str = Field(..., min_length=6, max_length=15)
    phone: str = Field(..., min_length=6, max_length=15)


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
