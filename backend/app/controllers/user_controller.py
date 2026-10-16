from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateSafe, UserPasswordUpdate
from app.services.user_service import UserService
from app.core.security import verify_password, get_password_hash
from typing import List
from app.schemas.company import CompanyOperatorMembershipResponse
from app.services.company_service import CompanyService

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute)

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/me/companies", response_model=List[CompanyOperatorMembershipResponse])
def get_my_companies(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return CompanyService.get_operator_companies(db, str(current_user.user_id))

@router.put("/me", response_model=UserResponse)
def update_user_me(
    user_update: UserUpdateSafe,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return UserService.update_user(db, current_user.user_id, user_update)

@router.get("/me/dashboard")
def get_dashboard(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return UserService.get_dashboard_data(db, current_user.user_id)

@router.put("/me/password")
def update_password_me(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    UserService.update_password(db, current_user.user_id, password_data.old_password, password_data.new_password)
    return {"message": "Password updated successfully"}


@router.delete("/me", response_model=UserResponse)
def soft_delete_user_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return UserService.soft_delete_user(db, current_user.user_id)
