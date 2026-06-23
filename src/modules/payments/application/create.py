from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field
from src.modules.payments.domain.types import PaymentAccountType


class CreatePaymentAccountRequest(BaseModel):
    account_type: str = Field(
        ..., pattern="|".join(c.value for c in PaymentAccountType)
    )
    bank_name: str = Field(..., min_length=1, max_length=64)
    holder_document: str = Field(..., min_length=1, max_length=20)
    account_number: str | None = Field(default=None, min_length=1, max_length=30)
    account_holder: str | None = Field(default=None, min_length=1, max_length=128)
    phone_number: str | None = Field(default=None, min_length=1, max_length=15)


class UpdatePaymentAccountRequest(BaseModel):
    account_type: str | None = Field(
        default=None, pattern="|".join(c.value for c in PaymentAccountType)
    )
    bank_name: str | None = Field(default=None, min_length=1, max_length=64)
    holder_document: str | None = Field(default=None, min_length=1, max_length=20)
    account_number: str | None = Field(default=None, min_length=1, max_length=30)
    account_holder: str | None = Field(default=None, min_length=1, max_length=128)
    phone_number: str | None = Field(default=None, min_length=1, max_length=15)
    is_active: int | None = Field(default=None, ge=0, le=1)


class UserPaymentAccountDTO(BaseModel):
    id: UUID
    user_id: UUID
    account_type: str
    bank_name: str
    holder_document: str
    account_number: str | None
    account_holder: str | None
    phone_number: str | None
    is_active: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserPaymentAccountListDTO(BaseModel):
    accounts: list[UserPaymentAccountDTO]
