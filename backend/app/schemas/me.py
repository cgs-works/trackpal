from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    role: str
    username: str
    name: str | None = None
    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    is_active: bool | None = None
    created_at: datetime
    updated_at: datetime


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    name: str | None = None


class PasswordChange(BaseModel):
    old_password: str
    new_password: str
