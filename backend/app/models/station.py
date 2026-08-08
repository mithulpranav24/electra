import uuid
from sqlalchemy import Column, String, Boolean, Numeric, DateTime, Time, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geography
from app.core.database import Base

class Area(Base):
    __tablename__ = "areas"

    area_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

class Station(Base):
    __tablename__ = "stations"

    station_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.company_id", ondelete="RESTRICT"), nullable=False)
    area_id = Column(UUID(as_uuid=True), ForeignKey("areas.area_id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False)
    gps_coordinates = Column(Geography(geometry_type='POINT', srid=4326), nullable=False)
    price_per_kwh = Column(Numeric(10, 2), nullable=False)
    minimum_session_fee = Column(Numeric(10, 2), nullable=False, default=0.00)
    opening_time_local = Column(Time, nullable=True)
    closing_time_local = Column(Time, nullable=True)
    timezone = Column(String(50), nullable=False)
    current_shift_start_utc = Column(DateTime, nullable=True)
    current_shift_end_utc = Column(DateTime, nullable=True)
    locked_gate = Column(Boolean, nullable=False, default=False)
    locked_gate_at = Column(DateTime, nullable=True)
    is_deprecating = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    # relationships
    company = relationship("Company", back_populates="stations")
    ports = relationship("ChargingPort", back_populates="station", cascade="all, delete-orphan")

class ChargingPort(Base):
    __tablename__ = "charging_ports"

    port_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id", ondelete="RESTRICT"), nullable=False)
    qr_code = Column(String(100), unique=True, nullable=False)
    connector_type = Column(String(50), nullable=False)
    charger_type = Column(String(50), nullable=False)
    status = Column(String, nullable=False, default="Available")
    is_pending_maintenance = Column(Boolean, nullable=False, default=False)
    has_health_warning = Column(Boolean, nullable=False, default=False)
    has_blocked_warning = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    status_updated_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    # relationships
    station = relationship("Station", back_populates="ports")
