from sqlalchemy.orm import Session
from fastapi import HTTPException
from app.models.company import Company, CompanyOperatorMembership
from app.schemas.company import CompanyCreate, CompanyUpdate, CompanyOperatorMembershipCreate
import uuid

class CompanyService:
    @staticmethod
    def create_company(db: Session, company_in: CompanyCreate):
        db_company = Company(name=company_in.name)
        db.add(db_company)
        try:
            db.commit()
            db.refresh(db_company)
            return db_company
        except Exception:
            db.rollback()
            raise HTTPException(status_code=400, detail="Company name already exists or invalid data")

    @staticmethod
    def get_companies(db: Session):
        return db.query(Company).all()

    @staticmethod
    def get_company(db: Session, company_id: str):
        company = db.query(Company).filter(Company.company_id == company_id).first()
        if not company:
            raise HTTPException(status_code=404, detail="Company not found")
        return company

    @staticmethod
    def update_company(db: Session, company_id: str, company_in: CompanyUpdate):
        company = CompanyService.get_company(db, company_id)
        update_data = company_in.model_dump(exclude_unset=True)
        for key, value in update_data.items():
            setattr(company, key, value)
        
        db.add(company)
        db.commit()
        db.refresh(company)
        return company

    @staticmethod
    def assign_operator(db: Session, membership_in: CompanyOperatorMembershipCreate):
        # Check if already assigned
        existing = db.query(CompanyOperatorMembership).filter(
            CompanyOperatorMembership.company_id == membership_in.company_id,
            CompanyOperatorMembership.user_id == membership_in.user_id
        ).first()
        
        if existing:
            if not existing.is_active:
                existing.is_active = True
                db.commit()
                db.refresh(existing)
            return existing
            
        new_membership = CompanyOperatorMembership(
            company_id=membership_in.company_id,
            user_id=membership_in.user_id
        )
        db.add(new_membership)
        try:
            db.commit()
            db.refresh(new_membership)
            return new_membership
        except Exception:
            db.rollback()
            raise HTTPException(status_code=400, detail="Invalid company or user id")

    @staticmethod
    def get_operators(db: Session, company_id: str):
        return db.query(CompanyOperatorMembership).filter(CompanyOperatorMembership.company_id == company_id).all()

    @staticmethod
    def get_operator_companies(db: Session, user_id: str):
        return db.query(CompanyOperatorMembership).filter(
            CompanyOperatorMembership.user_id == user_id,
            CompanyOperatorMembership.is_active == True
        ).all()
