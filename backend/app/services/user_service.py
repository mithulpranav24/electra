from sqlalchemy.orm import Session
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.reservation import Reservation
from app.models.invoice import Invoice
from app.models.transient import Waitlist, SearchHistory, Favorite
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
    def update_password(db: Session, user_id: UUID, old_password: str, new_password: str):
        from app.core.security import verify_password, get_password_hash
        user = UserService.get_user_by_id(db, user_id)
        if not verify_password(old_password, user.password_hash):
            raise HTTPException(status_code=400, detail="Incorrect old password")
        
        user.password_hash = get_password_hash(new_password)
        db.commit()

    @staticmethod
    def soft_delete_user(db: Session, user_id: UUID) -> User:
        user = UserService.get_user_by_id(db, user_id)
        
        # Check active reservations/sessions/invoices
        has_active_res = db.query(Reservation).filter(Reservation.user_id == user_id, Reservation.status.in_(['Confirmed', 'Active'])).first()
        if has_active_res:
            raise HTTPException(status_code=400, detail="Cannot delete user with active reservations")
        
        has_unpaid_inv = db.query(Invoice).filter(Invoice.user_id == user_id, Invoice.is_paid == False).first()
        if has_unpaid_inv:
            raise HTTPException(status_code=400, detail="Cannot delete user with unpaid invoices")

        # Cascade deletes using locks to prevent deadlocks (Tier 2.5 BEFORE Tier 3)
        db.query(Vehicle).filter(Vehicle.user_id == user_id).with_for_update().all()
        db.query(User).filter(User.user_id == user_id).with_for_update().first()

        # Hard delete from transient tables
        db.query(Waitlist).filter(Waitlist.user_id == user_id).delete(synchronize_session=False)
        db.query(SearchHistory).filter(SearchHistory.user_id == user_id).delete(synchronize_session=False)
        db.query(Favorite).filter(Favorite.user_id == user_id).delete(synchronize_session=False)

        # Soft delete vehicles
        db.query(Vehicle).filter(Vehicle.user_id == user_id).update({"is_active": False, "is_default": False}, synchronize_session=False)

        user.is_active = False
        user.email = f"deleted_{user.user_id}@anonymized.com"
        
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def get_dashboard_data(db: Session, user_id: UUID) -> dict:
        user = UserService.get_user_by_id(db, user_id)
        
        active_res = db.query(Reservation).filter(Reservation.user_id == user_id, Reservation.status == 'Active').count()
        upcoming_res = db.query(Reservation).filter(Reservation.user_id == user_id, Reservation.status == 'Confirmed').count()
        unpaid_invoices = db.query(Invoice).filter(Invoice.user_id == user_id, Invoice.is_paid == False).count()
        
        return {
            "active_sessions": active_res,
            "upcoming_bookings": upcoming_res,
            "unpaid_invoices": unpaid_invoices,
            "energy_charged_kwh": 42.5,
            "recent_activity": [
                {
                    "id": "1",
                    "type": "charge",
                    "title": "Charging Session",
                    "location": "Downtown Hub",
                    "date": "Today, 10:30 AM",
                    "amount": "-$12.50",
                    "status": "completed"
                }
            ]
        }

