import uuid
from sqlalchemy import Column, String, Boolean, DateTime, Numeric, ForeignKey, func, text
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Reservation(Base):
    __tablename__ = 'reservations'
    reservation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.vehicle_id", ondelete="RESTRICT"), nullable=False)
    port_id = Column(UUID(as_uuid=True), ForeignKey("charging_ports.port_id", ondelete="RESTRICT"), nullable=False)
    status = Column(String, nullable=False, default='Confirmed')
    is_extended = Column(Boolean, nullable=False, default=False)
    is_from_waitlist = Column(Boolean, nullable=False, default=False)
    waitlist_joined_at = Column(DateTime, nullable=True)
    cancellation_reason = Column(String(255), nullable=True)
    status_updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    reserved_tariff = Column(Numeric(10, 2), nullable=False)
    # DD-02: expires_at is the authoritative expiry time (accounts for extensions)
    expires_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP + INTERVAL '15 minutes'"))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
