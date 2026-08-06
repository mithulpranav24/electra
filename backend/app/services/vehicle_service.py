from sqlalchemy.orm import Session
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
    def create_vehicle(db: Session, vehicle_in: VehicleCreate, user_id: UUID) -> Vehicle:
        # Check if the registration number is unique
        existing = db.query(Vehicle).filter(Vehicle.registration_number == vehicle_in.registration_number).first()
        if existing:
            raise HTTPException(status_code=400, detail="Registration number already in use")

        # Handle setting as default
        if vehicle_in.is_default:
            db.query(Vehicle).filter(Vehicle.user_id == user_id, Vehicle.is_default == True).update({"is_default": False})

        new_vehicle = Vehicle(
            **vehicle_in.dict(),
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

        if "is_default" in update_data and update_data["is_default"]:
            db.query(Vehicle).filter(Vehicle.user_id == user_id, Vehicle.is_default == True).update({"is_default": False})

        for key, value in update_data.items():
            setattr(vehicle, key, value)
        
        db.commit()
        db.refresh(vehicle)
        return vehicle

    @staticmethod
    def soft_delete_vehicle(db: Session, vehicle_id: UUID, user_id: UUID) -> Vehicle:
        vehicle = VehicleService.get_vehicle_by_id(db, vehicle_id)
        if vehicle.user_id != user_id:
            raise HTTPException(status_code=403, detail="Not authorized to delete this vehicle")
        
        # Soft-delete constraints check goes here
        vehicle.is_active = False
        vehicle.is_default = False
        db.commit()
        db.refresh(vehicle)
        return vehicle
