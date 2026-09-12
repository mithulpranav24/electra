from sqlalchemy.orm import Session
from sqlalchemy import func
from fastapi import HTTPException
from app.models.station import Station, ChargingPort
from app.models.company import CompanyOperatorMembership
from app.schemas.station import StationCreate, StationUpdate, ChargingPortCreate, ChargingPortUpdate
from app.services.audit_service import log_audit_event

class StationService:
    @staticmethod
    def _to_schema(db: Session, station: Station):
        # We need to extract lat/lng from gps_coordinates
        # We can do a quick DB query to get ST_X and ST_Y
        coords = db.query(func.ST_Y(station.gps_coordinates), func.ST_X(station.gps_coordinates)).first()
        station_dict = station.__dict__.copy()
        if coords:
            station_dict['lat'] = coords[0]
            station_dict['lng'] = coords[1]
        
        # Load ports
        station_dict['ports'] = station.ports
        return station_dict

    @staticmethod
    def _check_operator_permission(db: Session, user_id: str, company_id: str):
        # Admin bypass could be added here if we pass the user object, but we assume the caller checks
        membership = db.query(CompanyOperatorMembership).filter(
            CompanyOperatorMembership.user_id == user_id,
            CompanyOperatorMembership.company_id == company_id,
            CompanyOperatorMembership.is_active == True
        ).first()
        if not membership:
            raise HTTPException(status_code=403, detail="You do not have permission for this company's stations")

    @staticmethod
    def create_station(db: Session, user_id: str, company_id: str, station_in: StationCreate):
        StationService._check_operator_permission(db, user_id, company_id)
        
        wkt_point = f'SRID=4326;POINT({station_in.lng} {station_in.lat})'
        
        db_station = Station(
            company_id=company_id,
            name=station_in.name,
            gps_coordinates=wkt_point,
            price_per_kwh=station_in.price_per_kwh,
            minimum_session_fee=station_in.minimum_session_fee,
            timezone=station_in.timezone,
            opening_time_local=station_in.opening_time_local,
            closing_time_local=station_in.closing_time_local,
            locked_gate=station_in.locked_gate
        )
        db.add(db_station)
        try:
            db.commit()
            db.refresh(db_station)
            return StationService._to_schema(db, db_station)
        except Exception as e:
            db.rollback()
            raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")

    @staticmethod
    def get_stations_for_company(db: Session, company_id: str):
        stations = db.query(Station).filter(Station.company_id == company_id).all()
        return [StationService._to_schema(db, s) for s in stations]

    @staticmethod
    def update_station(db: Session, user_id: str, station_id: str, station_in: StationUpdate, ip_address: str = "unknown"):
        station = db.query(Station).filter(Station.station_id == station_id).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")

        StationService._check_operator_permission(db, user_id, str(station.company_id))

        update_data = station_in.model_dump(exclude_unset=True)

        if 'lat' in update_data and 'lng' in update_data:
            lat = update_data.pop('lat')
            lng = update_data.pop('lng')
            station.gps_coordinates = f'SRID=4326;POINT({lng} {lat})'
        elif 'lat' in update_data or 'lng' in update_data:
            # Need both to update
            raise HTTPException(status_code=400, detail="Both lat and lng must be provided to update coordinates")

        for key, value in update_data.items():
            setattr(station, key, value)

        log_audit_event(
            db,
            user_id=user_id,
            action="Station Updated",
            entity_type="STATIONS",
            entity_id=station.station_id,
            details={"fields": list(update_data.keys())},
            ip_address=ip_address,
            commit=False,
        )
        db.commit()
        db.refresh(station)
        return StationService._to_schema(db, station)

    @staticmethod
    def delete_station(db: Session, user_id: str, station_id: str):
        station = db.query(Station).filter(Station.station_id == station_id).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
            
        StationService._check_operator_permission(db, user_id, str(station.company_id))
        
        station.is_active = False
        db.commit()
        return {"detail": "Station deleted"}

    # Charging Port Methods
    @staticmethod
    def create_port(db: Session, user_id: str, station_id: str, port_in: ChargingPortCreate):
        station = db.query(Station).filter(Station.station_id == station_id).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
            
        StationService._check_operator_permission(db, user_id, str(station.company_id))
        
        db_port = ChargingPort(
            station_id=station_id,
            qr_code=port_in.qr_code,
            connector_type=port_in.connector_type,
            charger_type=port_in.charger_type,
            status=port_in.status or "Available"
        )
        db.add(db_port)
        try:
            db.commit()
            db.refresh(db_port)
            return db_port
        except Exception:
            db.rollback()
            raise HTTPException(status_code=400, detail="Invalid data or QR code already exists")

    @staticmethod
    def update_port(db: Session, user_id: str, port_id: str, port_in: ChargingPortUpdate, ip_address: str = "unknown"):
        port = db.query(ChargingPort).filter(ChargingPort.port_id == port_id).first()
        if not port:
            raise HTTPException(status_code=404, detail="Port not found")

        station = port.station
        StationService._check_operator_permission(db, user_id, str(station.company_id))

        update_data = port_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(port, key, value)

        log_audit_event(
            db,
            user_id=user_id,
            action="Station Updated",
            entity_type="CHARGING_PORTS",
            entity_id=port.port_id,
            details={"fields": list(update_data.keys())},
            ip_address=ip_address,
            commit=False,
        )
        db.commit()
        db.refresh(port)
        return port

    @staticmethod
    def delete_port(db: Session, user_id: str, port_id: str):
        port = db.query(ChargingPort).filter(ChargingPort.port_id == port_id).first()
        if not port:
            raise HTTPException(status_code=404, detail="Port not found")
            
        station = port.station
        StationService._check_operator_permission(db, user_id, str(station.company_id))
        
        port.is_active = False
        db.commit()
        return {"detail": "Port deleted"}
