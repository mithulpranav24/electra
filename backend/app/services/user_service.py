from sqlalchemy.orm import Session
from sqlalchemy import text
from app.models.user import User
from app.schemas.user import UserUpdateSafe
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
    def update_user(db: Session, user_id: UUID, user_update: UserUpdateSafe) -> User:
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
        
        # Check active reservations/sessions/invoices
        has_active_res = db.execute(text("SELECT 1 FROM reservations WHERE user_id = :uid AND status IN ('Confirmed', 'Active')"), {"uid": user_id}).first()
        if has_active_res:
            raise HTTPException(status_code=400, detail="Cannot delete user with active reservations")
        
        has_unpaid_inv = db.execute(text("SELECT 1 FROM invoices WHERE user_id = :uid AND is_paid = FALSE"), {"uid": user_id}).first()
        if has_unpaid_inv:
            raise HTTPException(status_code=400, detail="Cannot delete user with unpaid invoices")

        # Cascade deletes using locks to prevent deadlocks
        db.execute(text("SELECT 1 FROM users WHERE user_id = :uid FOR UPDATE"), {"uid": user_id})
        db.execute(text("SELECT 1 FROM vehicles WHERE user_id = :uid FOR UPDATE"), {"uid": user_id})

        # Hard delete from transient tables
        db.execute(text("DELETE FROM waitlist WHERE user_id = :uid"), {"uid": user_id})
        db.execute(text("DELETE FROM search_history WHERE user_id = :uid"), {"uid": user_id})
        db.execute(text("DELETE FROM favorites WHERE user_id = :uid"), {"uid": user_id})

        # Soft delete vehicles
        db.execute(text("UPDATE vehicles SET is_active = FALSE, is_default = FALSE WHERE user_id = :uid"), {"uid": user_id})

        user.is_active = False
        user.email = f"deleted_{user.user_id}@anonymized.com"
        
        db.commit()
        db.refresh(user)
        return user
