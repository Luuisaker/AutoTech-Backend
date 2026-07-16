from pydantic import BaseModel, Field, field_validator
from src.utils.venezuelan_validators import validate_phone as _validate_phone


class UpdateUserRequest(BaseModel):
    first_name: str | None = Field(default=None, min_length=2, max_length=64)
    last_name: str | None = Field(default=None, min_length=2, max_length=64)
    phone: str | None = Field(default=None, min_length=6, max_length=15)
    language_preference: str | None = None

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return _validate_phone(v)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)
