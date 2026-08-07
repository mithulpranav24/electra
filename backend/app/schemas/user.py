from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    wallet_balance: Optional[float] = None
    is_suspended: Optional[bool] = None
    is_active: Optional[bool] = None
    banned_until: Optional[datetime] = None

class UserUpdateSafe(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    id: UUID = Field(alias="user_id")
    user_id: UUID
    role: str
    wallet_balance: float
    is_suspended: bool
    is_active: bool
    banned_until: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
