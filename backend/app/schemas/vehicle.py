from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class VehicleBase(BaseModel):
    registration_number: str = Field(..., max_length=50)
    battery_capacity: float = Field(..., ge=2.0, le=250.0)
    connector_type: str = Field(..., max_length=50)

class VehicleCreate(VehicleBase):
    is_default: Optional[bool] = False

class VehicleUpdate(BaseModel):
    registration_number: Optional[str] = Field(None, max_length=50)
    battery_capacity: Optional[float] = Field(None, ge=2.0, le=250.0)
    connector_type: Optional[str] = Field(None, max_length=50)
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

class VehicleResponse(VehicleBase):
    vehicle_id: UUID
    user_id: UUID
    is_default: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
