from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdate
from app.services.user_service import UserService

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user_me(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return UserService.update_user(db, current_user.user_id, user_update)

@router.delete("/me", response_model=UserResponse)
def soft_delete_user_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return UserService.soft_delete_user(db, current_user.user_id)
