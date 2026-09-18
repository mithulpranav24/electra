import uuid
from sqlalchemy import Column, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class MaintenanceSchedule(Base):
    __tablename__ = "maintenance_schedules"

    maintenance_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    port_id = Column(UUID(as_uuid=True), ForeignKey("charging_ports.port_id", ondelete="CASCADE"), nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=False)
    status = Column(String(50), nullable=False, default="Scheduled")
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
