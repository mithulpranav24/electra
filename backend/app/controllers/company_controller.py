from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.dependencies import require_admin
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyResponse, CompanyOperatorMembershipCreate, CompanyOperatorMembershipResponse
from app.services.company_service import CompanyService
from app.models.user import User

router = APIRouter()

@router.post("/", response_model=CompanyResponse)
def create_company(company_in: CompanyCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return CompanyService.create_company(db, company_in)

@router.get("/", response_model=List[CompanyResponse])
def get_companies(db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return CompanyService.get_companies(db)

@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(company_id: str, company_in: CompanyUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return CompanyService.update_company(db, company_id, company_in)

@router.post("/memberships", response_model=CompanyOperatorMembershipResponse)
def assign_operator(membership_in: CompanyOperatorMembershipCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return CompanyService.assign_operator(db, membership_in)

@router.get("/{company_id}/memberships", response_model=List[CompanyOperatorMembershipResponse])
def get_operators(company_id: str, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    return CompanyService.get_operators(db, company_id)
