from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    phone_e164: str = Field(min_length=8, max_length=20)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
