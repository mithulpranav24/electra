import uuid
from sqlalchemy import Column, String, Boolean, Numeric, DateTime, ForeignKey, func, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Vehicle(Base):
    __tablename__ = "vehicles"

    vehicle_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    registration_number = Column(String(50), unique=True, nullable=False)
    battery_capacity = Column(Numeric(5, 2), nullable=False)
    connector_type = Column(String(50), nullable=False)
    is_default = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    __table_args__ = (
        CheckConstraint('battery_capacity >= 2 AND battery_capacity <= 250', name='vehicles_battery_capacity_check'),
    )
