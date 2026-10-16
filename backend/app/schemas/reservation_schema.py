from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class ReservationCreate(BaseModel):
    vehicle_id: str
    station_id: Optional[str] = None
    port_id: Optional[str] = None
    # Driver-chosen check-in window (minutes). Defaults to the 15-minute SLA;
    # the controller clamps this to the allowed 15–120 range.
    grace_period_minutes: Optional[int] = 15

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
    # Port/station context so the driver can see — and check in with — the
    # reserved port's QR code without digging back into the station page.
    port_qr_code: Optional[str] = None
    port_qr_token: Optional[str] = None
    connector_type: Optional[str] = None
    charger_type: Optional[str] = None
    station_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
