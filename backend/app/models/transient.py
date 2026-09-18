import uuid
from sqlalchemy import Column, DateTime, Numeric, String, Text, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Waitlist(Base):
    __tablename__ = 'waitlist'
    waitlist_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), unique=True, nullable=False)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id", ondelete="CASCADE"), nullable=False)
    vehicle_id = Column(UUID(as_uuid=True), ForeignKey("vehicles.vehicle_id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
    joined_tariff = Column(Numeric(10, 2), nullable=False)
    joined_minimum_fee = Column(Numeric(10, 2), nullable=False)
    offered_port_id = Column(UUID(as_uuid=True), ForeignKey("charging_ports.port_id", ondelete="SET NULL"), nullable=True)
    offered_at = Column(DateTime, nullable=True)

class FaultExemptionClaim(Base):
    __tablename__ = 'fault_exemption_claims'
    claim_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    waitlist_id = Column(UUID(as_uuid=True), nullable=True)
    port_id = Column(UUID(as_uuid=True), ForeignKey("charging_ports.port_id", ondelete="CASCADE"), nullable=False)
    claimed_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

class WaitlistRejection(Base):
    __tablename__ = 'waitlist_rejections'
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), primary_key=True)
    port_id = Column(UUID(as_uuid=True), ForeignKey("charging_ports.port_id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

class SearchHistory(Base):
    __tablename__ = 'search_history'
    search_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    search_query = Column(Text, nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

class Favorite(Base):
    __tablename__ = 'favorites'
    favorite_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

class RecentStation(Base):
    __tablename__ = 'recent_stations'
    recent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id", ondelete="CASCADE"), nullable=False)
    viewed_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
