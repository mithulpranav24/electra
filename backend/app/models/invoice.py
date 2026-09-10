import uuid
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Numeric, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Invoice(Base):
    __tablename__ = 'invoices'
    invoice_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    charging_session_id = Column(UUID(as_uuid=True), ForeignKey("charging_sessions.session_id", ondelete="RESTRICT"), unique=True, nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="RESTRICT"), nullable=False)
    total_amount = Column(Numeric(10, 2), nullable=False)
    is_paid = Column(Boolean, nullable=False, default=False)
    paid_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
