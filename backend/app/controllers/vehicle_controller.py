from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from uuid import UUID
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.vehicle import VehicleCreate, VehicleResponse, VehicleUpdate
from app.services.vehicle_service import VehicleService

router = APIRouter()

@router.post("/", response_model=VehicleResponse)
def create_vehicle(
    vehicle_in: VehicleCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return VehicleService.create_vehicle(db, vehicle_in, current_user.user_id)

@router.get("/", response_model=List[VehicleResponse])
def get_vehicles(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return VehicleService.get_user_vehicles(db, current_user.user_id)

@router.get("/{vehicle_id}", response_model=VehicleResponse)
def get_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return VehicleService.get_vehicle_by_id(db, vehicle_id, current_user.user_id)


@router.put("/{vehicle_id}", response_model=VehicleResponse)
def update_vehicle(
    vehicle_id: UUID,
    vehicle_in: VehicleUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return VehicleService.update_vehicle(db, vehicle_id, current_user.user_id, vehicle_in)

@router.delete("/{vehicle_id}", response_model=VehicleResponse)
def delete_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return VehicleService.soft_delete_vehicle(db, vehicle_id, current_user.user_id)

@router.post("/{vehicle_id}/default", response_model=VehicleResponse)
def set_default_vehicle(
    vehicle_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return VehicleService.set_default_vehicle(db, vehicle_id, current_user.user_id)
