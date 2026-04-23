from pydantic import BaseModel, Field
from uuid import UUID
from app.enums import UserTypeEnum


class LoginRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"


class OTPRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20)


class OTPVerifyRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20)
    code: str = Field(min_length=4, max_length=8)


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserOut(BaseModel):
    id: UUID
    phone_e164: str
    user_type: UserTypeEnum | None = None
    first_name: str | None = None
    last_name: str | None = None

    class Config:
        from_attributes = True


class UserRoleUpdateRequest(BaseModel):
    user_type: UserTypeEnum
