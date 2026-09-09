from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.reservation import Reservation
from app.models.station import ChargingPort, Station
from app.models.transient import Waitlist
from app.models.user import User
from app.models.vehicle import Vehicle

ESCROW_AMOUNT = Decimal("1000.00")
OFFER_WINDOW_SECONDS = 90
GPS_RADIUS_METERS = 2000
CLOSING_BUFFER_MINUTES = 32
SLA_GRACE_PERIOD_MINUTES = 15
STANDARD_COOLDOWN_MINUTES = 60


class WaitlistService:
    # ------------------------------------------------------------------
    # Promotion helpers, shared by the reservation-expiry cleanup, manual
    # cancellation, and the background waitlist-offer-expiry worker.
    # ------------------------------------------------------------------
    @staticmethod
    def find_candidate_waitlist_entry(db: Session, station_id, connector_type) -> Optional[Waitlist]:
        """Locks (FOR UPDATE) and returns the earliest eligible waitlist entry for a
        freed port at this station/connector, or None if the queue is empty.
        Callers must already hold the STATIONS -> CHARGING_PORTS -> VEHICLES -> USERS
        locks per the global lock hierarchy before calling this, so the WAITLIST
        (tier 3.5) lock is acquired strictly before any RESERVATIONS (tier 4) lock.
        """
        # Flush first so a prior promotion/deletion earlier in the same transaction
        # (e.g. another port at this station being processed in the same batch job)
        # is visible to this SELECT before the next candidate is picked.
        db.flush()
        return (
            db.query(Waitlist)
            .join(Vehicle, Waitlist.vehicle_id == Vehicle.vehicle_id)
            .filter(
                Waitlist.station_id == station_id,
                Waitlist.offered_port_id.is_(None),
                Vehicle.connector_type == connector_type,
            )
            .order_by(Waitlist.joined_at.asc())
            .with_for_update(of=Waitlist)
            .first()
        )

    @staticmethod
    def apply_promotion_or_release(db: Session, port: ChargingPort, candidate: Optional[Waitlist]) -> Optional[Waitlist]:
        """Given a port that just became free and an already-locked candidate
        waitlist entry (or None), either offers the port to the candidate or
        releases it back to Available. A port carrying a health/blocked warning
        skips promotion entirely (Arch 3.3.3) and stays a manual walk-in option.
        """
        if port.has_health_warning or port.has_blocked_warning:
            port.status = "Available"
            return None

        if candidate is not None:
            port.status = "Pending Waitlist"
            candidate.offered_port_id = port.port_id
            candidate.offered_at = datetime.now(timezone.utc).replace(tzinfo=None)
            return candidate

        port.status = "Available"
        return None

    # ------------------------------------------------------------------
    # Join / status / leave
    # ------------------------------------------------------------------
    @staticmethod
    def _assert_within_gps_radius(db: Session, station_id: str, lat: float, lng: float) -> None:
        point = f"SRID=4326;POINT({lng} {lat})"
        distance = db.execute(
            text("SELECT ST_Distance(gps_coordinates, ST_GeogFromText(:point)) FROM stations WHERE station_id = :station_id"),
            {"point": point, "station_id": station_id},
        ).scalar()
        if distance is None:
            raise HTTPException(status_code=404, detail="Station not found")
        if distance > GPS_RADIUS_METERS:
            raise HTTPException(status_code=400, detail=f"You must be within {GPS_RADIUS_METERS / 1000:.0f}km of the station to join its waitlist")

    @staticmethod
    def join_waitlist(db: Session, current_user, request, ip_address: str) -> Waitlist:
        existing = db.query(Waitlist).filter(Waitlist.user_id == current_user.user_id).first()
        if existing:
            raise HTTPException(status_code=409, detail="You already have an active waitlist entry")

        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == request.vehicle_id).first()
        if not vehicle:
            raise HTTPException(status_code=404, detail="Vehicle not found")

        WaitlistService._assert_within_gps_radius(db, request.station_id, request.lat, request.lng)

        try:
            db.execute(
                text("CALL sp_JoinWaitlist(:p_user_id, :p_station_id, :p_vehicle_id, :p_closing_buffer_minutes)"),
                {
                    "p_user_id": current_user.user_id,
                    "p_station_id": request.station_id,
                    "p_vehicle_id": request.vehicle_id,
                    "p_closing_buffer_minutes": CLOSING_BUFFER_MINUTES,
                },
            )
            db.commit()
        except Exception as e:
            db.rollback()
            error_msg = str(e)
            if "already has an active waitlist entry" in error_msg:
                raise HTTPException(status_code=409, detail="You already have an active waitlist entry")
            elif "An available port exists" in error_msg:
                raise HTTPException(status_code=400, detail="An available port exists; reserve it directly instead of joining the waitlist")
            elif "No operational ports" in error_msg:
                raise HTTPException(status_code=404, detail="No operational ports for this connector type at this station")
            elif "Insufficient wallet balance" in error_msg:
                raise HTTPException(status_code=400, detail=f"Insufficient wallet balance. Minimum ₹{ESCROW_AMOUNT} + minimum session fee required.")
            elif "closing too soon" in error_msg:
                raise HTTPException(status_code=400, detail="Station is closing too soon to join the waitlist")
            elif "banned" in error_msg:
                raise HTTPException(status_code=403, detail="User is banned")
            elif "Station not found" in error_msg or "Vehicle not found" in error_msg:
                raise HTTPException(status_code=404, detail=error_msg.split("\n")[0])
            else:
                raise HTTPException(status_code=400, detail=error_msg.split("\n")[0])

        new_entry = (
            db.query(Waitlist)
            .filter(Waitlist.user_id == current_user.user_id, Waitlist.station_id == request.station_id)
            .order_by(Waitlist.joined_at.desc())
            .first()
        )
        if not new_entry:
            raise HTTPException(status_code=500, detail="Failed to retrieve created waitlist entry")

        db.add(AuditLog(
            user_id=current_user.user_id,
            action="Waitlist Joined",
            entity_type="WAITLIST",
            entity_id=new_entry.waitlist_id,
            details={"station_id": str(request.station_id), "vehicle_id": str(request.vehicle_id)},
            ip_address=str(ip_address),
        ))
        db.commit()
        return new_entry

    @staticmethod
    def get_status(db: Session, current_user) -> Optional[Waitlist]:
        return db.query(Waitlist).filter(Waitlist.user_id == current_user.user_id).first()

    @staticmethod
    def get_queue_position(db: Session, entry: Waitlist) -> int:
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == entry.vehicle_id).first()
        connector_type = vehicle.connector_type if vehicle else None
        ahead = (
            db.query(Waitlist)
            .join(Vehicle, Waitlist.vehicle_id == Vehicle.vehicle_id)
            .filter(
                Waitlist.station_id == entry.station_id,
                Vehicle.connector_type == connector_type,
                Waitlist.joined_at < entry.joined_at,
            )
            .count()
        )
        return ahead + 1

    @staticmethod
    def leave_waitlist(db: Session, current_user, ip_address: str) -> None:
        entry_read = db.query(Waitlist).filter(Waitlist.user_id == current_user.user_id).first()
        if not entry_read:
            raise HTTPException(status_code=404, detail="You do not have an active waitlist entry")

        # Lock order: STATIONS -> CHARGING_PORTS (if an offer is held) -> VEHICLES -> USERS -> WAITLIST
        db.query(Station).with_for_update().filter(Station.station_id == entry_read.station_id).first()

        port = None
        if entry_read.offered_port_id:
            port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == entry_read.offered_port_id).first()

        db.query(Vehicle).with_for_update().filter(Vehicle.vehicle_id == entry_read.vehicle_id).first()
        db.query(User).with_for_update().filter(User.user_id == current_user.user_id).first()

        entry = db.query(Waitlist).with_for_update().filter(Waitlist.waitlist_id == entry_read.waitlist_id).first()
        if not entry:
            db.rollback()
            raise HTTPException(status_code=404, detail="You do not have an active waitlist entry")

        db.delete(entry)

        if port is not None and port.status == "Pending Waitlist":
            candidate = WaitlistService.find_candidate_waitlist_entry(db, entry.station_id, port.connector_type)
            WaitlistService.apply_promotion_or_release(db, port, candidate)

        db.add(AuditLog(
            user_id=current_user.user_id,
            action="Waitlist Left",
            entity_type="WAITLIST",
            entity_id=entry.waitlist_id,
            details={"station_id": str(entry.station_id)},
            ip_address=str(ip_address),
        ))
        db.commit()

    # ------------------------------------------------------------------
    # Offer confirmation
    # ------------------------------------------------------------------
    @staticmethod
    def confirm_offer(db: Session, current_user, waitlist_id: str, ip_address: str) -> Reservation:
        entry = db.query(Waitlist).filter(
            Waitlist.waitlist_id == waitlist_id,
            Waitlist.user_id == current_user.user_id,
        ).first()
        if not entry:
            raise HTTPException(status_code=404, detail="Waitlist entry not found")
        if not entry.offered_port_id:
            raise HTTPException(status_code=400, detail="No active offer to confirm")

        # sp_ConfirmWaitlist deletes this WAITLIST row on success, and the session
        # expires committed objects by default — capture what we need up front so
        # we never touch `entry`'s attributes again after the commit below.
        offered_port_id = entry.offered_port_id

        try:
            db.execute(
                text("""
                    CALL sp_ConfirmWaitlist(
                        :p_user_id, :p_waitlist_id, :p_port_id,
                        :p_grace_period_minutes, :p_cooldown_minutes, :p_ip_address
                    )
                """),
                {
                    "p_user_id": current_user.user_id,
                    "p_waitlist_id": waitlist_id,
                    "p_port_id": offered_port_id,
                    "p_grace_period_minutes": SLA_GRACE_PERIOD_MINUTES,
                    "p_cooldown_minutes": STANDARD_COOLDOWN_MINUTES,
                    "p_ip_address": str(ip_address),
                },
            )
            db.commit()
        except Exception as e:
            db.rollback()
            error_msg = str(e)
            if "offer expired" in error_msg:
                raise HTTPException(status_code=410, detail="Waitlist offer has expired")
            elif "Insufficient wallet balance" in error_msg:
                raise HTTPException(status_code=400, detail="Insufficient wallet balance to confirm this offer")
            elif "already has an active reservation" in error_msg:
                raise HTTPException(status_code=400, detail="You already have an active reservation")
            elif "not Pending Waitlist" in error_msg or "IDOR check failed" in error_msg:
                raise HTTPException(status_code=409, detail="This offer is no longer valid")
            elif "cancellation cooldown" in error_msg:
                raise HTTPException(status_code=400, detail="You are in a cancellation cooldown for this station")
            else:
                raise HTTPException(status_code=400, detail=error_msg.split("\n")[0])

        new_res = (
            db.query(Reservation)
            .filter(Reservation.user_id == current_user.user_id, Reservation.port_id == offered_port_id)
            .order_by(Reservation.created_at.desc())
            .first()
        )
        if not new_res:
            raise HTTPException(status_code=500, detail="Failed to retrieve created reservation")

        db.add(AuditLog(
            user_id=current_user.user_id,
            action="Waitlist Offer Confirmed",
            entity_type="RESERVATIONS",
            entity_id=new_res.reservation_id,
            details={"port_id": str(offered_port_id), "waitlist_id": str(waitlist_id)},
            ip_address=str(ip_address),
        ))
        db.commit()
        return new_res

    # ------------------------------------------------------------------
    # Background worker entry point (DD-03: 90 second exclusive deadline)
    # ------------------------------------------------------------------
    @staticmethod
    def expire_stale_offers(db: Session) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(seconds=OFFER_WINDOW_SECONDS)
        stale_entries = db.query(Waitlist).filter(
            Waitlist.offered_port_id.isnot(None),
            Waitlist.offered_at <= cutoff,
        ).all()

        expired_count = 0
        for stale in stale_entries:
            port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == stale.offered_port_id).first()
            entry = db.query(Waitlist).with_for_update().filter(Waitlist.waitlist_id == stale.waitlist_id).first()
            if not entry or not port:
                continue
            # Re-check under lock: another request may have confirmed/left in the meantime.
            if entry.offered_at is None or entry.offered_at > cutoff:
                continue

            db.delete(entry)
            candidate = WaitlistService.find_candidate_waitlist_entry(db, port.station_id, port.connector_type)
            WaitlistService.apply_promotion_or_release(db, port, candidate)

            db.add(AuditLog(
                user_id=entry.user_id,
                action="Waitlist Offer Expired",
                entity_type="WAITLIST",
                entity_id=entry.waitlist_id,
                details={"port_id": str(port.port_id)},
                ip_address="system",
            ))
            expired_count += 1

        if expired_count:
            db.commit()
        return expired_count
