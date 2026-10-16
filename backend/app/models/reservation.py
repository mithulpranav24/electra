import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, ForeignKey, func, text
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import ENUM, UUID
from app.core.database import Base

reservation_status_enum = ENUM(
    'Confirmed', 'Active', 'Expired', 'Cancelled', 'Completed',
    name='reservation_status_enum',
    create_type=False,
)

class Reservation(Base):
    __tablename__ = 'reservations'
    reservation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.vehicle_id", ondelete="RESTRICT"), nullable=False)
    port_id = Column(UUID(as_uuid=True), ForeignKey("charging_ports.port_id", ondelete="RESTRICT"), nullable=False)
    status = Column(reservation_status_enum, nullable=False, default='Confirmed')
    is_extended = Column(Boolean, nullable=False, default=False)
    is_from_waitlist = Column(Boolean, nullable=False, default=False)
    waitlist_joined_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(String(255), nullable=True)
    status_updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    reserved_tariff = Column(Numeric(10, 2), nullable=False)
    # DD-02: expires_at is the authoritative expiry time (accounts for extensions)
    expires_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP + INTERVAL '15 minutes'"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    port = relationship("ChargingPort")
    vehicle = relationship("Vehicle")

    @property
    def port_qr_code(self):
        return self.port.qr_code if self.port else None

    @property
    def port_qr_token(self):
        return str(self.port.qr_token) if (self.port and self.port.qr_token) else None

    @property
    def connector_type(self):
        return self.port.connector_type if self.port else None

    @property
    def charger_type(self):
        return self.port.charger_type if self.port else None

    @property
    def station_name(self):
        return self.port.station.name if (self.port and self.port.station) else None

    @property
    def vehicle_name(self):
        if not self.vehicle:
            return None
        parts = [p for p in (self.vehicle.make, self.vehicle.model) if p]
        label = " ".join(parts) if parts else None
        plate = self.vehicle.registration_number
        return f"{label} ({plate})" if label else plate
