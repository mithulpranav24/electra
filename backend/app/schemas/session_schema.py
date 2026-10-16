from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class SessionStartRequest(BaseModel):
    reservation_id: UUID
    initial_battery_percentage: Decimal
    target_battery_percentage: Decimal
    qr_code: str = ""
    latitude: Decimal = Decimal(0)
    longitude: Decimal = Decimal(0)

class SessionStatusResponse(BaseModel):
    session_id: UUID
    reservation_id: UUID
    port_id: UUID
    vehicle_id: UUID
    initial_battery_percentage: Decimal
    target_battery_percentage: Decimal
    applied_tariff: Decimal
    start_time: datetime
    current_battery_percentage: Decimal
    target_reached: bool
    energy_delivered_kwh: Decimal
    energy_cost: Decimal
    idle_minutes: Decimal
    idle_fee: Decimal
    total_cost: Decimal
    elapsed_minutes: Decimal
    eta_minutes_remaining: Decimal

    model_config = ConfigDict(from_attributes=True)


class ChallengePortRequest(BaseModel):
    latitude: Decimal = Decimal(0)
    longitude: Decimal = Decimal(0)
    qr_code: str = ""
    vehicle_id: Optional[UUID] = None


class ChallengePortResponse(BaseModel):
    success: bool
    message: str
    reservation_id: Optional[UUID] = None
    port_status: str

