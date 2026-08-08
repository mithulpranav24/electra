import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base

class Company(Base):
    __tablename__ = "companies"

    company_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), unique=True, nullable=False)
    is_deprecating = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    # relationships
    operator_memberships = relationship("CompanyOperatorMembership", back_populates="company", cascade="all, delete-orphan")
    stations = relationship("Station", back_populates="company")

class CompanyOperatorMembership(Base):
    __tablename__ = "company_operator_memberships"

    membership_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.company_id", ondelete="CASCADE"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    assigned_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())

    # relationships
    company = relationship("Company", back_populates="operator_memberships")
    # user relationship is defined on User model (or we can define it one-sided here)
    user = relationship("User")
