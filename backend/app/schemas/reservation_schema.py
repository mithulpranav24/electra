from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class ReservationCreate(BaseModel):
    vehicle_id: str
    station_id: Optional[str] = None
    port_id: Optional[str] = None

class CancelReservationRequest(BaseModel):
    reason: Optional[str] = None


class ReservationResponse(BaseModel):
    reservation_id: UUID
    user_id: UUID
    vehicle_id: UUID
    port_id: UUID
    status: str
    reserved_tariff: Decimal
    expires_at: datetime
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
