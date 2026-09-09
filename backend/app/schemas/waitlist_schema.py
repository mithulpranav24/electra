from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class WaitlistJoinRequest(BaseModel):
    station_id: str
    vehicle_id: str
    lat: float
    lng: float

class WaitlistStatusResponse(BaseModel):
    waitlist_id: UUID
    station_id: UUID
    vehicle_id: UUID
    joined_at: datetime
    joined_tariff: Decimal
    joined_minimum_fee: Decimal
    position: int
    offered_port_id: Optional[UUID] = None
    offered_at: Optional[datetime] = None
    offer_expires_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)
