from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from datetime import datetime
from uuid import UUID

class CompanyBase(BaseModel):
    name: str

class CompanyCreate(CompanyBase):
    pass

class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    is_deprecating: Optional[bool] = None
    is_active: Optional[bool] = None

class CompanyResponse(CompanyBase):
    company_id: UUID
    is_deprecating: bool
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CompanyOperatorMembershipCreate(BaseModel):
    company_id: UUID
    user_id: UUID

class CompanyOperatorMembershipResponse(BaseModel):
    membership_id: UUID
    company_id: UUID
    user_id: UUID
    is_active: bool
    assigned_at: datetime

    model_config = ConfigDict(from_attributes=True)
