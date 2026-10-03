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
        
        # Check if user is banned
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if user.banned_until and user.banned_until > now:
            raise HTTPException(status_code=400, detail="Banned users cannot delete their accounts")

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
        from app.models.session import ChargingSession
        from app.models.station import ChargingPort, Station

        user = UserService.get_user_by_id(db, user_id)
        
        active_res = db.query(Reservation).filter(Reservation.user_id == user_id, Reservation.status == 'Active').count()
        upcoming_res = db.query(Reservation).filter(Reservation.user_id == user_id, Reservation.status == 'Confirmed').count()
        unpaid_invoices = db.query(Invoice).filter(Invoice.user_id == user_id, Invoice.is_paid == False).count()

        # Real total energy delivered across all completed, non-aborted sessions for this user
        completed_sessions = (
            db.query(ChargingSession, Vehicle, ChargingPort, Station)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .join(Vehicle, Reservation.vehicle_id == Vehicle.vehicle_id)
            .join(ChargingPort, Reservation.port_id == ChargingPort.port_id)
            .join(Station, ChargingPort.station_id == Station.station_id)
            .filter(
                Reservation.user_id == user_id,
                ChargingSession.end_time.isnot(None),
                ChargingSession.is_aborted.is_(False),
            )
            .all()
        )
        total_kwh = sum(
            float(compute_snapshot(s, v, p, st, s.end_time)["energy_delivered_kwh"])
            for s, v, p, st in completed_sessions
        )


        # Last 5 completed sessions with station/invoice info
        recent_sessions = (
            db.query(ChargingSession, Reservation, Station, Invoice)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .join(ChargingPort, Reservation.port_id == ChargingPort.port_id)
            .join(Station, ChargingPort.station_id == Station.station_id)
            .outerjoin(Invoice, Invoice.charging_session_id == ChargingSession.session_id)
            .filter(
                Reservation.user_id == user_id,
                ChargingSession.end_time.isnot(None),
                ChargingSession.is_aborted.is_(False),
            )
            .order_by(ChargingSession.end_time.desc())
            .limit(5)
            .all()
        )


        recent_activity = []
        for session, reservation, station, invoice in recent_sessions:
            recent_activity.append({
                "id": str(session.session_id),
                "type": "charge",
                "title": "Charging Session",
                "location": station.name,
                "date": session.end_time.strftime("%Y-%m-%d %H:%M") if session.end_time else "Unknown",
                "amount": f"-₹{float(invoice.total_amount):.2f}" if invoice else "-₹0.00",
                "status": "completed",
            })

        return {
            "active_sessions": active_res,
            "upcoming_bookings": upcoming_res,
            "unpaid_invoices": unpaid_invoices,
            "energy_charged_kwh": round(float(total_kwh), 2),
            "recent_activity": recent_activity,
        }

