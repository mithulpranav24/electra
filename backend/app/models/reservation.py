import uuid
from sqlalchemy import Column, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Reservation(Base):
    __tablename__ = 'reservations'
    reservation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    vehicle_id = Column(UUID(as_uuid=True))
    status = Column(String)
