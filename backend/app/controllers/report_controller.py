from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_admin, require_operator
from app.models.user import User
from app.schemas.report_schema import AdminReportResponse, OperatorReportResponse
from app.services.report_service import ReportService
from app.services.station_service import StationService

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute)


@router.get("/admin", response_model=AdminReportResponse)
def get_admin_report(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return ReportService.get_admin_report(db)


@router.get("/operator/{company_id}", response_model=OperatorReportResponse)
def get_operator_report(company_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_operator)):
    StationService._check_operator_permission(db, str(current_user.user_id), str(company_id))
    return ReportService.get_operator_report(db, str(company_id))
