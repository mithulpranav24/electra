import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class ChargingSession(Base):
    __tablename__ = 'charging_sessions'

    session_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reservation_id = Column(UUID(as_uuid=True), ForeignKey("reservations.reservation_id", ondelete="RESTRICT"), nullable=False)
    initial_battery_percentage = Column(Numeric(5, 2), nullable=False)
    target_battery_percentage = Column(Numeric(5, 2), nullable=False)
    applied_tariff = Column(Numeric(10, 2), nullable=False)
    is_overstay_penalized = Column(Boolean, nullable=False, default=False)
    hardware_acked = Column(Boolean, nullable=False, default=False)
    hardware_ack_deadline = Column(DateTime, nullable=True)
    hardware_state = Column(String(20), nullable=False, default='Connected')
    is_aborted = Column(Boolean, nullable=False, default=False)
    start_time = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    idle_start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    cumulative_closure_seconds = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

