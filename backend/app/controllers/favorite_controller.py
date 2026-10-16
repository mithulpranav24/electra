from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.station import Station
from app.models.transient import Favorite
from app.schemas.station import StationResponse
from app.services.station_service import StationService

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute, prefix="/favorites", tags=["Favorites"])

class FavoriteResponse(BaseModel):
    favorite_id: UUID
    station_id: UUID
    station: StationResponse
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

@router.get("", response_model=List[FavoriteResponse])
def get_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    favorites = db.query(Favorite).filter(Favorite.user_id == current_user.user_id).all()
    
    result = []
    for fav in favorites:
        station = db.query(Station).filter(Station.station_id == fav.station_id).first()
        if station:
            fav_dict = fav.__dict__.copy()
            fav_dict['station'] = StationService._to_schema(db, station)
            result.append(fav_dict)
            
    return result

@router.post("/{station_id}")
def add_favorite(
    station_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(Favorite).filter(
        Favorite.user_id == current_user.user_id,
        Favorite.station_id == station_id
    ).first()
    
    if existing:
        return {"message": "Already a favorite"}

    fav = Favorite(user_id=current_user.user_id, station_id=station_id)
    db.add(fav)
    db.commit()
    return {"message": "Added to favorites"}

@router.delete("/{station_id}")
def remove_favorite(
    station_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    fav = db.query(Favorite).filter(
        Favorite.user_id == current_user.user_id,
        Favorite.station_id == station_id
    ).first()
    
    if fav:
        db.delete(fav)
        db.commit()
        
    return {"message": "Removed from favorites"}
