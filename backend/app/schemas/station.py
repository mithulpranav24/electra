from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List
from datetime import datetime, time
from uuid import UUID
from decimal import Decimal

class ChargingPortBase(BaseModel):
    qr_code: str
    connector_type: str
    charger_type: str
    status: Optional[str] = "Available"

class ChargingPortCreate(ChargingPortBase):
    pass

class ChargingPortUpdate(BaseModel):
    qr_code: Optional[str] = None
    connector_type: Optional[str] = None
    charger_type: Optional[str] = None
    status: Optional[str] = None
    is_pending_maintenance: Optional[bool] = None
    has_health_warning: Optional[bool] = None
    has_blocked_warning: Optional[bool] = None
    is_active: Optional[bool] = None

class ChargingPortResponse(ChargingPortBase):
    port_id: UUID
    station_id: UUID
    is_pending_maintenance: bool
    has_health_warning: bool
    has_blocked_warning: bool
    is_active: bool
    status_updated_at: datetime
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StationBase(BaseModel):
    name: str
    price_per_kwh: Decimal
    minimum_session_fee: Decimal = Decimal("0.00")
    timezone: str
    opening_time_local: Optional[time] = None
    closing_time_local: Optional[time] = None
    locked_gate: bool = False
    
class StationCreate(StationBase):
    lat: float
    lng: float

class StationUpdate(BaseModel):
    name: Optional[str] = None
    price_per_kwh: Optional[Decimal] = None
    minimum_session_fee: Optional[Decimal] = None
    timezone: Optional[str] = None
    opening_time_local: Optional[time] = None
    closing_time_local: Optional[time] = None
    locked_gate: Optional[bool] = None
    is_deprecating: Optional[bool] = None
    is_active: Optional[bool] = None
    lat: Optional[float] = None
    lng: Optional[float] = None

class StationResponse(StationBase):
    station_id: UUID
    company_id: UUID
    area_id: Optional[UUID] = None
    is_deprecating: bool
    is_active: bool
    created_at: datetime
    # Coordinates for frontend mapping
    lat: float
    lng: float
    ports: List[ChargingPortResponse] = []

    model_config = ConfigDict(from_attributes=True)
