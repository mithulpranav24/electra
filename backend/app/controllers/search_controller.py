from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.station import Station, ChargingPort
from app.models.transient import RecentStation
from app.schemas.station import StationResponse
from app.schemas.search_schema import StationSearchRequest
from app.services.station_service import StationService

router = APIRouter(prefix="/search", tags=["Search"])

@router.post("/stations", response_model=List[StationResponse])
def search_stations(
    request: StationSearchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # PostGIS ST_DWithin query:
    # We create a Point from the lat/lng. Geography takes 'SRID=4326;POINT(lng lat)'
    # radius is in meters (radius_km * 1000)
    point = f'SRID=4326;POINT({request.lng} {request.lat})'
    
    query = db.query(Station).filter(
        Station.is_active == True,
        Station.is_deprecating == False,
        func.ST_DWithin(Station.gps_coordinates, func.ST_GeogFromText(point), request.radius_km * 1000)
    )
    
    if request.connector_type or request.min_power_kw:
        query = query.join(ChargingPort)
        if request.connector_type:
            query = query.filter(ChargingPort.connector_type == request.connector_type)
        if request.min_power_kw:
            query = query.filter(Station.price_per_kwh >= 0) # Placeholder if power is added later, or filter differently
            # For now, PRD doesn't enforce min_power_kw natively on Port, but we can filter if needed.
            pass
        query = query.filter(ChargingPort.is_active == True)
        
    stations = query.all()
    
    # Use the existing service helper to map lat/lng
    return [StationService._to_schema(db, s) for s in stations]

@router.get("/stations/{station_id}", response_model=StationResponse)
def get_station(
    station_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    station = db.query(Station).filter(
        Station.station_id == station_id,
        Station.is_active == True,
        Station.is_deprecating == False
    ).first()
    
    if not station:
        raise HTTPException(status_code=404, detail="Station not found")
        
    # Log recent station
    existing_recent = db.query(RecentStation).filter(
        RecentStation.user_id == current_user.user_id,
        RecentStation.station_id == station_id
    ).first()
    
    if existing_recent:
        existing_recent.viewed_at = func.now()
    else:
        new_recent = RecentStation(user_id=current_user.user_id, station_id=station_id)
        db.add(new_recent)
    db.commit()
        
    return StationService._to_schema(db, station)

@router.get("/recent", response_model=List[StationResponse])
def get_recent_stations(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    recent_records = db.query(RecentStation).filter(
        RecentStation.user_id == current_user.user_id
    ).order_by(RecentStation.viewed_at.desc()).limit(5).all()
    
    stations = []
    for record in recent_records:
        station = db.query(Station).filter(
            Station.station_id == record.station_id,
            Station.is_active == True,
            Station.is_deprecating == False
        ).first()
        if station:
            stations.append(StationService._to_schema(db, station))
            
    return stations

