from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.core.database import get_db
from app.core.dependencies import require_operator
from app.schemas.station import StationCreate, StationUpdate, StationResponse, ChargingPortCreate, ChargingPortUpdate, ChargingPortResponse
from app.schemas.reservation_schema import ReservationResponse
from app.services.station_service import StationService
from app.models.user import User
from app.models.station import Station, ChargingPort
from app.models.reservation import Reservation

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute)

def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"

@router.post("/company/{company_id}", response_model=StationResponse)
def create_station(company_id: str, station_in: StationCreate, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    return StationService.create_station(db, str(current_user.user_id), company_id, station_in)

@router.get("/company/{company_id}", response_model=List[StationResponse])
def get_stations(company_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    # Operators can see stations for their company, checking could be done in service or here.
    # Service doesn't check for GET currently since it's just a listing, but it's safe if UI restricts it.
    StationService._check_operator_permission(db, str(current_user.user_id), company_id)
    return StationService.get_stations_for_company(db, company_id)

@router.put("/{station_id}", response_model=StationResponse)
def update_station(station_id: str, station_in: StationUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    return StationService.update_station(db, str(current_user.user_id), station_id, station_in, _client_ip(request))

@router.delete("/{station_id}")
def delete_station(station_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    return StationService.delete_station(db, str(current_user.user_id), station_id)

# Port Endpoints
@router.post("/{station_id}/ports", response_model=ChargingPortResponse)
def create_port(station_id: str, port_in: ChargingPortCreate, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    return StationService.create_port(db, str(current_user.user_id), station_id, port_in)

@router.put("/ports/{port_id}", response_model=ChargingPortResponse)
def update_port(port_id: str, port_in: ChargingPortUpdate, request: Request, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    return StationService.update_port(db, str(current_user.user_id), port_id, port_in, _client_ip(request))

@router.delete("/ports/{port_id}")
def delete_port(port_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    return StationService.delete_port(db, str(current_user.user_id), port_id)

@router.get("/company/{company_id}/reservations/active", response_model=List[ReservationResponse])
def get_active_reservations_for_company(company_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    StationService._check_operator_permission(db, str(current_user.user_id), company_id)
    station_ids = db.query(Station.station_id).filter(Station.company_id == company_id).scalar_subquery()
    port_ids = db.query(ChargingPort.port_id).filter(ChargingPort.station_id.in_(station_ids)).scalar_subquery()
    reservations = (
        db.query(Reservation)
        .options(joinedload(Reservation.port).joinedload(ChargingPort.station), joinedload(Reservation.vehicle))
        .filter(Reservation.port_id.in_(port_ids), Reservation.status.in_(["Confirmed", "Active"]))
        .order_by(Reservation.created_at.desc())
        .all()
    )
    return reservations
