from sqlalchemy.orm import Session
from app.models.vehicle import Vehicle
from app.models.user import User
from app.models.reservation import Reservation
from app.models.transient import Waitlist
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from fastapi import HTTPException
from uuid import UUID

class VehicleService:
    @staticmethod
    def get_vehicle_by_id(db: Session, vehicle_id: UUID, user_id: UUID = None) -> Vehicle:
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        if user_id and vehicle.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        return vehicle

    @staticmethod
    def _set_default_locks(db: Session, user_id: UUID):
        # Tier 2.5 and Tier 3 locks (Tier 2.5 must be locked before Tier 3)
        db.query(Vehicle).filter(Vehicle.user_id == user_id).with_for_update().all()
        db.query(User).filter(User.user_id == user_id).with_for_update().first()
        
        # Fetch all current default vehicles for the user (should be at most 1)
        old_defaults = db.query(Vehicle).filter(Vehicle.user_id == user_id, Vehicle.is_default == True).all()
        for old_default in old_defaults:
            old_default.is_default = False
            
        # Flush the session to ensure the database sees is_default=False 
        # before we set a new vehicle to is_default=True, avoiding UniqueViolation
        db.flush()

    @staticmethod
    def create_vehicle(db: Session, vehicle_in: VehicleCreate, user_id: UUID) -> Vehicle:
        existing = db.query(Vehicle).filter(Vehicle.registration_number == vehicle_in.registration_number).first()
        if existing:
            raise HTTPException(status_code=400, detail="Registration number already in use")

        if vehicle_in.is_default:
            VehicleService._set_default_locks(db, user_id)

        new_vehicle = Vehicle(
            **vehicle_in.dict(exclude_unset=True),
            user_id=user_id
        )
        db.add(new_vehicle)
        db.commit()
        db.refresh(new_vehicle)
        return new_vehicle

    @staticmethod
    def get_user_vehicles(db: Session, user_id: UUID):
        return db.query(Vehicle).filter(Vehicle.user_id == user_id, Vehicle.is_active == True).all()

    @staticmethod
    def update_vehicle(db: Session, vehicle_id: UUID, user_id: UUID, vehicle_in: VehicleUpdate) -> Vehicle:
        vehicle = VehicleService.get_vehicle_by_id(db, vehicle_id, user_id)
        
        update_data = vehicle_in.dict(exclude_unset=True)
        if "is_active" in update_data:
            del update_data["is_active"] # Prevent un-deleting via update

        # Mutation Safeguard (FR-2)
        if ("battery_capacity" in update_data and float(update_data["battery_capacity"]) != float(vehicle.battery_capacity)) or \
           ("connector_type" in update_data and update_data["connector_type"] != vehicle.connector_type):
            
            has_res = db.query(Reservation).filter(Reservation.vehicle_id == vehicle_id, Reservation.status.in_(['Confirmed', 'Active'])).first()
            if has_res:
                raise HTTPException(status_code=400, detail="Cannot modify battery/connector with active reservations")
            
            # Remove from waitlists
            db.query(Waitlist).filter(Waitlist.vehicle_id == vehicle_id).delete(synchronize_session=False)

        if update_data.get("is_default", False):
            VehicleService._set_default_locks(db, user_id)

        for key, value in update_data.items():
            setattr(vehicle, key, value)
        
        db.commit()
        db.refresh(vehicle)
        return vehicle
    
    @staticmethod
    def set_default_vehicle(db: Session, vehicle_id: UUID, user_id: UUID) -> Vehicle:
        vehicle = VehicleService.get_vehicle_by_id(db, vehicle_id, user_id)
        VehicleService._set_default_locks(db, user_id)
        vehicle.is_default = True
        db.commit()
        db.refresh(vehicle)
        return vehicle

    @staticmethod
    def soft_delete_vehicle(db: Session, vehicle_id: UUID, user_id: UUID) -> Vehicle:
        vehicle = VehicleService.get_vehicle_by_id(db, vehicle_id, user_id)
        
        # Soft-delete constraints check
        has_res = db.query(Reservation).filter(Reservation.vehicle_id == vehicle_id, Reservation.status.in_(['Confirmed', 'Active'])).first()
        if has_res:
            raise HTTPException(status_code=400, detail="Cannot delete vehicle with active reservations")
        
        # Hard delete waitlist entries
        db.query(Waitlist).filter(Waitlist.vehicle_id == vehicle_id).delete(synchronize_session=False)

        vehicle.is_active = False
        vehicle.is_default = False
        db.commit()
        db.refresh(vehicle)
        return vehicle

