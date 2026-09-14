from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_operator
from app.models.user import User
from app.schemas.maintenance_schema import MaintenanceScheduleCreate, MaintenanceScheduleResponse
from app.services.maintenance_service import MaintenanceService

router = APIRouter(prefix="/maintenance", tags=["Maintenance"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.post("", response_model=MaintenanceScheduleResponse)
def schedule_maintenance(
    payload: MaintenanceScheduleCreate,
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    return MaintenanceService.schedule_maintenance(db, current_user, payload, _client_ip(fastapi_req))


@router.get("/station/{station_id}", response_model=List[MaintenanceScheduleResponse])
def list_station_maintenance(
    station_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    return MaintenanceService.list_schedules_for_station(db, current_user, station_id)


@router.post("/{maintenance_id}/complete", response_model=MaintenanceScheduleResponse)
def complete_maintenance(
    maintenance_id: UUID,
    fastapi_req: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_operator),
):
    return MaintenanceService.complete_maintenance(db, current_user, maintenance_id, _client_ip(fastapi_req))
