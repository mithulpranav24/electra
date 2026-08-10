from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class ReservationCreate(BaseModel):
    port_id: str
    vehicle_id: str

class ReservationResponse(BaseModel):
    reservation_id: UUID
    user_id: UUID
    vehicle_id: UUID
    port_id: UUID
    status: str
    reserved_tariff: Decimal
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
