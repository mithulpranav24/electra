from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Optional
from datetime import datetime
from uuid import UUID

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    phone_number: Optional[str] = None

class UserCreate(UserBase):
    password: str = Field(..., min_length=8)

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        common_passwords = {'password', '12345678', 'password123', 'admin123', 'qwertyuiop', '11111111'}
        if v.lower() in common_passwords:
            raise ValueError("Password is too common or breached")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

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

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        common_passwords = {'password', '12345678', 'password123', 'admin123', 'qwertyuiop', '11111111'}
        if v.lower() in common_passwords:
            raise ValueError("Password is too common or breached")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

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
