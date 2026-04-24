from pydantic import BaseModel, Field
from uuid import UUID
from typing import Any
from app.enums import UserTypeEnum

PHONE_E164_PATTERN = r"^\+[1-9]\d{7,19}$"
OTP_CODE_PATTERN = r"^\d{4,8}$"


class LoginRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20, pattern=PHONE_E164_PATTERN)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class OTPRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20, pattern=PHONE_E164_PATTERN)


class OTPVerifyRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20, pattern=PHONE_E164_PATTERN)
    code: str = Field(min_length=4, max_length=8, pattern=OTP_CODE_PATTERN)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: UUID
    phone_e164: str
    user_type: UserTypeEnum | None = None
    first_name: str | None = None
    last_name: str | None = None
    relay_id: UUID | None = None
    notification_preferences: dict[str, Any] | None = None

    class Config:
        from_attributes = True


class UserRoleUpdateRequest(BaseModel):
    user_type: UserTypeEnum


class NotificationPreferencesUpdateRequest(BaseModel):
    sms_enabled: bool | None = None
    email_enabled: bool | None = None
    push_enabled: bool | None = None
    whatsapp_enabled: bool | None = None
    language: str | None = Field(default=None, min_length=2, max_length=10)
