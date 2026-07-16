from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)
    totp_code: str | None = None
    device_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TwoFactorSetupResponse(BaseModel):
    secret: str
    otpauth_uri: str


class TwoFactorVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6)


class TwoFactorStatusResponse(BaseModel):
    is_2fa_enabled: bool
