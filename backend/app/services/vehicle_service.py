from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.vehicle import Vehicle
from app.schemas.vehicle import VehicleCreate, VehicleUpdate
from fastapi import HTTPException
from uuid import UUID

class VehicleService:
    @staticmethod
    def get_vehicle_by_id(db: Session, vehicle_id: UUID) -> Vehicle:
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")
        return vehicle

    @staticmethod
    def _set_default_locks(db: Session, user_id: UUID):
        # Tier 2.5 and Tier 3 locks
        db.execute(text("SELECT 1 FROM vehicles WHERE user_id = :uid FOR UPDATE"), {"uid": user_id})
        db.execute(text("SELECT 1 FROM users WHERE user_id = :uid FOR UPDATE"), {"uid": user_id})
        db.execute(text("UPDATE vehicles SET is_default = FALSE WHERE user_id = :uid AND is_default = TRUE"), {"uid": user_id})

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
        vehicle = VehicleService.get_vehicle_by_id(db, vehicle_id)
        if vehicle.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to update this vehicle")
        
        update_data = vehicle_in.dict(exclude_unset=True)
        if "is_active" in update_data:
            del update_data["is_active"] # Prevent un-deleting via update

        # Mutation Safeguard (FR-2)
        if ("battery_capacity" in update_data and float(update_data["battery_capacity"]) != float(vehicle.battery_capacity)) or \
           ("connector_type" in update_data and update_data["connector_type"] != vehicle.connector_type):
            
            has_res = db.execute(text("SELECT 1 FROM reservations WHERE vehicle_id = :vid AND status IN ('Confirmed', 'Active')"), {"vid": vehicle_id}).first()
            if has_res:
                raise HTTPException(status_code=400, detail="Cannot modify battery/connector with active reservations")
            
            # Remove from waitlists
            db.execute(text("DELETE FROM waitlist WHERE vehicle_id = :vid"), {"vid": vehicle_id})

        if update_data.get("is_default", False):
            VehicleService._set_default_locks(db, user_id)

        for key, value in update_data.items():
            setattr(vehicle, key, value)
        
        db.commit()
        db.refresh(vehicle)
        return vehicle
    
    @staticmethod
    def set_default_vehicle(db: Session, vehicle_id: UUID, user_id: UUID) -> Vehicle:
        vehicle = VehicleService.get_vehicle_by_id(db, vehicle_id)
        if vehicle.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized")
        VehicleService._set_default_locks(db, user_id)
        vehicle.is_default = True
        db.commit()
        db.refresh(vehicle)
        return vehicle

    @staticmethod
    def soft_delete_vehicle(db: Session, vehicle_id: UUID, user_id: UUID) -> Vehicle:
        vehicle = VehicleService.get_vehicle_by_id(db, vehicle_id)
        if vehicle.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this vehicle")
        
        # Soft-delete constraints check
        has_res = db.execute(text("SELECT 1 FROM reservations WHERE vehicle_id = :vid AND status IN ('Confirmed', 'Active')"), {"vid": vehicle_id}).first()
        if has_res:
            raise HTTPException(status_code=400, detail="Cannot delete vehicle with active reservations")
        
        # Hard delete waitlist entries
        db.execute(text("DELETE FROM waitlist WHERE vehicle_id = :vid"), {"vid": vehicle_id})

        vehicle.is_active = False
        vehicle.is_default = False
        db.commit()
        db.refresh(vehicle)
        return vehicle
