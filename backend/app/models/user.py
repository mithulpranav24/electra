import uuid
from sqlalchemy import Column, String, Boolean, Numeric, DateTime, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class User(Base):
    __tablename__ = "users"

    user_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    role = Column(String(50), nullable=False, default="Driver")
    wallet_balance = Column(Numeric(10, 2), nullable=False, default=0.00)
    banned_until = Column(DateTime, nullable=True)
    is_suspended = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    vehicles = relationship("Vehicle", back_populates="user")
