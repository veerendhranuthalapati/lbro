from __future__ import annotations
import re
from pydantic import BaseModel, EmailStr, Field, field_validator


def _validate_password(v: str) -> str:
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[0-9]", v):
        raise ValueError("Password must contain at least one digit")
    return v


class LoginRequest(BaseModel):
    email: str = Field(min_length=1)  # plain str: no TLD validation at login
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        return _validate_password(v)


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str | None = Field(default=None, min_length=3, max_length=100)
    full_name: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=8)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _validate_password(v)


class ProfileUpdateRequest(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: EmailStr | None = None
    new_password: str | None = Field(default=None, min_length=8)
    current_password: str | None = None

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_password(v)
        return v
