import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.models.station import Station, ChargingPort
from app.models.transient import RecentStation, SearchHistory
from app.schemas.station import StationResponse
from app.schemas.search_schema import SearchHistoryEntry, StationSearchRequest
from app.services.station_service import StationService

router = APIRouter(prefix="/search", tags=["Search"])

SEARCH_HISTORY_LIMIT = 20

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
    
    # Calculate distance for sorting
    distance = func.ST_Distance(Station.gps_coordinates, func.ST_GeogFromText(point)).label('distance')
    
    query = db.query(Station, distance).filter(
        Station.is_active == True,
        Station.is_deprecating == False,
        func.ST_DWithin(Station.gps_coordinates, func.ST_GeogFromText(point), request.radius_km * 1000)
    )
    
    if request.connector_type or request.min_power_kw:
        query = query.join(ChargingPort)
        if request.connector_type:
            query = query.filter(ChargingPort.connector_type == request.connector_type)
        if request.min_power_kw:
            # Map power to charger_type heuristics since power_kw is not stored natively
            if request.min_power_kw > 22.0:
                query = query.filter(ChargingPort.charger_type.in_(["Fast", "Ultra-Fast", "DCFC"]))
            elif request.min_power_kw > 7.0:
                query = query.filter(ChargingPort.charger_type.in_(["Level 2", "Fast", "Ultra-Fast", "DCFC"]))
                
        query = query.filter(ChargingPort.is_active == True)
        
    query = query.order_by(distance)
    results = query.all()

    # FR-22 Search History: securely store the driver's own past searches
    # (area + filters) so they can be surfaced back as suggestions later.
    search_payload = {
        "lat": request.lat,
        "lng": request.lng,
        "radius_km": request.radius_km,
        "connector_type": request.connector_type,
        "min_power_kw": request.min_power_kw,
    }
    db.add(SearchHistory(user_id=current_user.user_id, search_query=json.dumps(search_payload)))
    db.commit()

    # results is a list of tuples (Station, distance)
    # We need to add distance to the schema if needed, or just return sorted stations
    stations = []
    for s, dist in results:
        s_schema = StationService._to_schema(db, s)
        # Assuming frontend might want distance_km if added to StationResponse in the future
        # s_schema['distance_km'] = dist / 1000.0
        stations.append(s_schema)
        
    return stations

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


@router.get("/history", response_model=List[SearchHistoryEntry])
def get_search_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    records = (
        db.query(SearchHistory)
        .filter(SearchHistory.user_id == current_user.user_id)
        .order_by(SearchHistory.created_at.desc())
        .limit(SEARCH_HISTORY_LIMIT)
        .all()
    )

    history = []
    for record in records:
        try:
            payload = json.loads(record.search_query)
        except (TypeError, ValueError):
            continue
        history.append(
            SearchHistoryEntry(
                search_id=record.search_id,
                lat=payload.get("lat"),
                lng=payload.get("lng"),
                radius_km=payload.get("radius_km"),
                connector_type=payload.get("connector_type"),
                min_power_kw=payload.get("min_power_kw"),
                created_at=record.created_at,
            )
        )
    return history


@router.delete("/history")
def clear_search_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db.query(SearchHistory).filter(SearchHistory.user_id == current_user.user_id).delete()
    db.commit()
    return {"message": "Search history cleared"}

