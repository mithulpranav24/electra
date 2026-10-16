from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.rating_schema import RatingCreate, RatingResponse, StationRatingsResponse
from app.services.rating_service import RatingService

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute, prefix="/ratings", tags=["Ratings"])


@router.post("/{station_id}", response_model=RatingResponse)
def submit_rating(
    station_id: UUID,
    payload: RatingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "Driver":
        raise HTTPException(status_code=403, detail="Only drivers can rate stations")
    return RatingService.submit_rating(db, current_user, station_id, payload)


@router.get("/{station_id}", response_model=StationRatingsResponse)
def get_station_ratings(
    station_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RatingService.get_station_ratings(db, station_id, current_user)
