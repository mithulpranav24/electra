import uuid
from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Waitlist(Base):
    __tablename__ = 'waitlist'
    waitlist_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    vehicle_id = Column(UUID(as_uuid=True))

class SearchHistory(Base):
    __tablename__ = 'search_history'
    search_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))

class Favorite(Base):
    __tablename__ = 'favorites'
    favorite_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    station_id = Column(UUID(as_uuid=True))
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

class RecentStation(Base):
    __tablename__ = 'recent_stations'
    recent_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    station_id = Column(UUID(as_uuid=True))
    viewed_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
