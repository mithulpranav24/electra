from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class VehicleBase(BaseModel):
    registration_number: str = Field(..., max_length=50, alias="license_plate")
    make: Optional[str] = None
    model: Optional[str] = None
    battery_capacity: float = Field(..., ge=2.0, le=250.0, alias="battery_capacity_kwh")
    connector_type: str = Field(..., max_length=50)

class VehicleCreate(VehicleBase):
    is_default: Optional[bool] = False

class VehicleUpdate(BaseModel):
    registration_number: Optional[str] = Field(None, max_length=50, alias="license_plate")
    make: Optional[str] = None
    model: Optional[str] = None
    battery_capacity: Optional[float] = Field(None, ge=2.0, le=250.0, alias="battery_capacity_kwh")
    connector_type: Optional[str] = Field(None, max_length=50)
    is_default: Optional[bool] = None

class VehicleResponse(VehicleBase):
    id: UUID = Field(alias="vehicle_id")
    vehicle_id: UUID
    user_id: UUID
    is_default: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
