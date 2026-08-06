from pydantic import BaseModel, EmailStr, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)
    role: Optional[str] = "Driver"

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    role: Optional[str] = None
    wallet_balance: Optional[float] = None
    is_suspended: Optional[bool] = None
    is_active: Optional[bool] = None
    banned_until: Optional[datetime] = None

class UserPasswordUpdate(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=8)

class UserResponse(UserBase):
    user_id: UUID
    role: str
    wallet_balance: float
    is_suspended: bool
    is_active: bool
    banned_until: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
