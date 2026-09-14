from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.rating import Rating
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.schemas.rating_schema import RatingCreate

RATING_LIST_LIMIT = 20


class RatingService:
    @staticmethod
    def _has_completed_session_at_station(db: Session, user_id: UUID, station_id: UUID) -> bool:
        """FR-20: ratings are restricted to drivers who have actually
        completed a charging session at the station, since cleanliness/access/
        experience scores are meaningless from someone who never physically
        visited."""
        return (
            db.query(ChargingSession.session_id)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .join(ChargingPort, Reservation.port_id == ChargingPort.port_id)
            .filter(
                Reservation.user_id == user_id,
                ChargingPort.station_id == station_id,
                ChargingSession.end_time.isnot(None),
            )
            .first()
            is not None
        )

    @staticmethod
    def submit_rating(db: Session, current_user, station_id: UUID, payload: RatingCreate) -> Rating:
        station = db.query(Station).filter(Station.station_id == station_id, Station.is_active.is_(True)).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")

        if not RatingService._has_completed_session_at_station(db, current_user.user_id, station_id):
            raise HTTPException(status_code=403, detail="You can only rate stations where you have completed a charging session")

        # UNIQUE(user_id, station_id): a re-submission updates the existing
        # rating rather than erroring, so drivers can revise their review.
        rating = db.query(Rating).filter(Rating.user_id == current_user.user_id, Rating.station_id == station_id).first()
        if rating:
            rating.overall_score = payload.overall_score
            rating.cleanliness_score = payload.cleanliness_score
            rating.access_score = payload.access_score
            rating.experience_score = payload.experience_score
            rating.comment = payload.comment
        else:
            rating = Rating(
                user_id=current_user.user_id,
                station_id=station_id,
                overall_score=payload.overall_score,
                cleanliness_score=payload.cleanliness_score,
                access_score=payload.access_score,
                experience_score=payload.experience_score,
                comment=payload.comment,
            )
            db.add(rating)

        db.commit()
        db.refresh(rating)
        return rating

    @staticmethod
    def get_station_ratings(db: Session, station_id: UUID, current_user=None) -> dict:
        summary_row = (
            db.query(
                func.count(Rating.rating_id),
                func.avg(Rating.overall_score),
                func.avg(Rating.cleanliness_score),
                func.avg(Rating.access_score),
                func.avg(Rating.experience_score),
            )
            .filter(Rating.station_id == station_id)
            .first()
        )
        count, avg_overall, avg_clean, avg_access, avg_exp = summary_row

        ratings = (
            db.query(Rating)
            .filter(Rating.station_id == station_id)
            .order_by(Rating.created_at.desc())
            .limit(RATING_LIST_LIMIT)
            .all()
        )

        my_rating: Optional[Rating] = None
        if current_user is not None:
            my_rating = db.query(Rating).filter(Rating.user_id == current_user.user_id, Rating.station_id == station_id).first()

        return {
            "summary": {
                "rating_count": count or 0,
                "average_overall": float(avg_overall) if avg_overall is not None else None,
                "average_cleanliness": float(avg_clean) if avg_clean is not None else None,
                "average_access": float(avg_access) if avg_access is not None else None,
                "average_experience": float(avg_exp) if avg_exp is not None else None,
            },
            "ratings": ratings,
            "my_rating": my_rating,
        }
