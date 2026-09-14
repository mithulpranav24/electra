from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime
from uuid import UUID


class RatingCreate(BaseModel):
    overall_score: int = Field(..., ge=1, le=5)
    cleanliness_score: int = Field(..., ge=1, le=5)
    access_score: int = Field(..., ge=1, le=5)
    experience_score: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


class RatingResponse(BaseModel):
    rating_id: UUID
    user_id: UUID
    station_id: UUID
    overall_score: int
    cleanliness_score: int
    access_score: int
    experience_score: int
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StationRatingSummary(BaseModel):
    rating_count: int
    average_overall: Optional[float] = None
    average_cleanliness: Optional[float] = None
    average_access: Optional[float] = None
    average_experience: Optional[float] = None


class StationRatingsResponse(BaseModel):
    summary: StationRatingSummary
    ratings: List[RatingResponse]
    my_rating: Optional[RatingResponse] = None
