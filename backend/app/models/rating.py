import uuid
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from app.core.database import Base


class Rating(Base):
    __tablename__ = "ratings"
    __table_args__ = (
        UniqueConstraint("user_id", "station_id", name="ratings_user_id_station_id_key"),
        CheckConstraint("overall_score BETWEEN 1 AND 5", name="ratings_overall_score_check"),
        CheckConstraint("cleanliness_score BETWEEN 1 AND 5", name="ratings_cleanliness_score_check"),
        CheckConstraint("access_score BETWEEN 1 AND 5", name="ratings_access_score_check"),
        CheckConstraint("experience_score BETWEEN 1 AND 5", name="ratings_experience_score_check"),
    )

    rating_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.user_id", ondelete="CASCADE"), nullable=False)
    station_id = Column(UUID(as_uuid=True), ForeignKey("stations.station_id", ondelete="CASCADE"), nullable=False)
    overall_score = Column(Integer, nullable=False)
    cleanliness_score = Column(Integer, nullable=False)
    access_score = Column(Integer, nullable=False)
    experience_score = Column(Integer, nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.current_timestamp())
