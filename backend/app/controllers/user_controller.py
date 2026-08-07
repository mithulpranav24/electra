from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.user import UserResponse, UserUpdateSafe, UserPasswordUpdate
from app.services.user_service import UserService
from app.core.security import verify_password, get_password_hash

router = APIRouter()

@router.get("/me", response_model=UserResponse)
def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.put("/me", response_model=UserResponse)
def update_user_me(
    user_update: UserUpdateSafe,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return UserService.update_user(db, current_user.user_id, user_update)

@router.put("/me/password")
def update_password_me(
    password_data: UserPasswordUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    from fastapi import HTTPException
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Incorrect old password")
    
    current_user.password_hash = get_password_hash(password_data.new_password)
    db.commit()
    return {"message": "Password updated successfully"}

@router.delete("/me", response_model=UserResponse)
def soft_delete_user_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    return UserService.soft_delete_user(db, current_user.user_id)
