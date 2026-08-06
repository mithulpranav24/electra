from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserUpdate
from fastapi import HTTPException
from uuid import UUID

class UserService:
    @staticmethod
    def get_user_by_id(db: Session, user_id: UUID) -> User:
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return user

    @staticmethod
    def update_user(db: Session, user_id: UUID, user_update: UserUpdate) -> User:
        user = UserService.get_user_by_id(db, user_id)
        update_data = user_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(user, key, value)
        
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def soft_delete_user(db: Session, user_id: UUID) -> User:
        user = UserService.get_user_by_id(db, user_id)
        
        # Soft-delete constraints checking should go here, e.g. checking active reservations/invoices
        # Assuming validations pass:
        user.is_active = False
        user.email = f"deleted_{user.user_id}@anonymized.com"
        
        db.commit()
        db.refresh(user)
        return user
