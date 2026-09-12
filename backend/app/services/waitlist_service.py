from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, or_, text
from sqlalchemy.orm import Session

from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.models.transient import Waitlist, WaitlistRejection
from app.models.user import User
from app.models.vehicle import Vehicle
from app.services.audit_service import log_audit_event
from app.services.penalty_service import PenaltyService

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
    def find_candidate_waitlist_entry(db: Session, station_id, connector_type, port_id=None) -> Optional[Waitlist]:
        """Single monolithic query (Architecture.md 3.3.3): optimistically (no row
        locks) reads USERS, VEHICLES, CHARGING_SESSIONS, RESERVATIONS, and
        WAITLIST_REJECTIONS to mathematically filter out banned, soft-deleted,
        busy, or previously-rejected drivers, then applies FOR UPDATE LIMIT 1
        ONLY to the winning WAITLIST row (no SKIP LOCKED, to preserve strict FIFO).
        Callers must already hold the STATIONS -> CHARGING_PORTS -> VEHICLES ->
        USERS locks per the global lock hierarchy before calling this, so the
        WAITLIST (tier 3.5) lock is acquired strictly before any RESERVATIONS
        (tier 4) lock.
        """
        # Flush first so a prior promotion/deletion earlier in the same transaction
        # (e.g. another port at this station being processed in the same batch job)
        # is visible to this SELECT before the next candidate is picked.
        db.flush()

        has_active_reservation = (
            db.query(Reservation.reservation_id)
            .filter(Reservation.user_id == Waitlist.user_id, Reservation.status.in_(["Confirmed", "Active"]))
            .correlate(Waitlist)
            .exists()
        )
        has_active_session = (
            db.query(ChargingSession.session_id)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .filter(Reservation.vehicle_id == Waitlist.vehicle_id, ChargingSession.end_time.is_(None))
            .correlate(Waitlist)
            .exists()
        )

        query = (
            db.query(Waitlist.waitlist_id)
            .join(Vehicle, Waitlist.vehicle_id == Vehicle.vehicle_id)
            .join(User, Waitlist.user_id == User.user_id)
            .filter(
                Waitlist.station_id == station_id,
                Waitlist.offered_port_id.is_(None),
                Vehicle.connector_type == connector_type,
                Vehicle.is_active.is_(True),
                User.is_active.is_(True),
                or_(User.banned_until.is_(None), User.banned_until <= func.current_timestamp()),
                ~has_active_reservation,
                ~has_active_session,
            )
        )
        if port_id is not None:
            has_rejected_this_port = (
                db.query(WaitlistRejection.user_id)
                .filter(WaitlistRejection.user_id == Waitlist.user_id, WaitlistRejection.port_id == port_id)
                .correlate(Waitlist)
                .exists()
            )
            query = query.filter(~has_rejected_this_port)

        eligible_id = query.order_by(Waitlist.joined_at.asc()).limit(1).scalar_subquery()

        return (
            db.query(Waitlist)
            .filter(Waitlist.waitlist_id == eligible_id)
            .with_for_update(of=Waitlist)
            .first()
        )

    @staticmethod
    def _station_closing_too_soon(db: Session, port: ChargingPort) -> bool:
        """Architecture.md 3.3.3: never offer a port if CURRENT_TIMESTAMP + 30
        minutes would exceed the station's closing time (insufficient time left
        to arrive and check in)."""
        station = db.query(Station).filter(Station.station_id == port.station_id).first()
        if not station or station.current_shift_end_utc is None:
            return False
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        return now + timedelta(minutes=30) > station.current_shift_end_utc

    @staticmethod
    def _is_last_operational_port(db: Session, port: ChargingPort) -> bool:
        other_operational = (
            db.query(ChargingPort)
            .filter(
                ChargingPort.station_id == port.station_id,
                ChargingPort.connector_type == port.connector_type,
                ChargingPort.port_id != port.port_id,
                ChargingPort.is_active.is_(True),
                ChargingPort.status.notin_(["Offline", "Maintenance"]),
            )
            .count()
        )
        return other_operational == 0

    @staticmethod
    def apply_promotion_or_release(db: Session, port: ChargingPort, candidate: Optional[Waitlist]) -> Optional[Waitlist]:
        """Given a port that just became free and an already-locked candidate
        waitlist entry (or None), either offers the port to the candidate or
        releases it back to Available. A port carrying a health/blocked warning
        skips promotion entirely (Arch 3.3.3) and stays a manual walk-in option -
        UNLESS it is the last operational port at the station for its connector
        type, in which case it transitions to Maintenance instead, so the queue
        does not trap indefinitely on a port nobody can promote into.
        """
        if port.has_health_warning or port.has_blocked_warning:
            port.status = "Maintenance" if WaitlistService._is_last_operational_port(db, port) else "Available"
            return None

        if WaitlistService._station_closing_too_soon(db, port):
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

        log_audit_event(
            db,
            user_id=current_user.user_id,
            action="Waitlist Joined",
            entity_type="WAITLIST",
            entity_id=new_entry.waitlist_id,
            details={"station_id": str(request.station_id), "vehicle_id": str(request.vehicle_id)},
            ip_address=str(ip_address),
        )
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
        # STATIONS is a read-only validation lock here (no station-wide state changes), so it
        # must be FOR SHARE (Architecture.md 3.5) rather than the exclusive default, or every
        # other concurrent reservation/waitlist request at this station would be blocked.
        db.query(Station).with_for_update(read=True).filter(Station.station_id == entry_read.station_id).first()

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
            # Architecture.md 3.3.3 Rule 7: leaving while holding an active offer
            # is processed as an ignored offer (1 penalty point), even though the
            # entry itself is removed rather than left for the offer to expire.
            PenaltyService.assign_penalty_point(db, current_user, "Ignored Waitlist Offer")
            candidate = WaitlistService.find_candidate_waitlist_entry(db, entry.station_id, port.connector_type, port.port_id)
            WaitlistService.apply_promotion_or_release(db, port, candidate)

        log_audit_event(
            db,
            user_id=current_user.user_id,
            action="Waitlist Left",
            entity_type="WAITLIST",
            entity_id=entry.waitlist_id,
            details={"station_id": str(entry.station_id)},
            ip_address=str(ip_address),
            commit=False,
        )
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

        log_audit_event(
            db,
            user_id=current_user.user_id,
            action="Waitlist Offer Confirmed",
            entity_type="RESERVATIONS",
            entity_id=new_res.reservation_id,
            details={"port_id": str(offered_port_id), "waitlist_id": str(waitlist_id)},
            ip_address=str(ip_address),
        )
        return new_res

    # ------------------------------------------------------------------
    # Background worker entry point (DD-03: 90 second exclusive deadline)
    # ------------------------------------------------------------------
    @staticmethod
    def expire_stale_offers(db: Session) -> int:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(seconds=OFFER_WINDOW_SECONDS)

        # Optimistic read only, per Architecture.md 3.4 - no locks yet. Ordered by the
        # port each offer holds (ascending PK, per the 3.5 "within a tier, ascending
        # primary key" rule) so that if two expiries happen to touch related rows,
        # every worker run and every concurrent process locks them in the same order.
        stale_ids = [
            row[0]
            for row in db.query(Waitlist.waitlist_id)
            .filter(Waitlist.offered_port_id.isnot(None), Waitlist.offered_at <= cutoff)
            .order_by(Waitlist.offered_port_id.asc())
            .all()
        ]

        expired_count = 0
        for waitlist_id in stale_ids:
            # Each stale offer is processed as its own atomic transaction (commit or
            # rollback per iteration) rather than one batch commit at the end, so a
            # lock wait or failure on one port can never block or deadlock another.
            optimistic = db.query(Waitlist).filter(Waitlist.waitlist_id == waitlist_id).first()
            if not optimistic or not optimistic.offered_port_id:
                continue

            # Tier 1: STATIONS FOR SHARE (read-only validation, no station-wide change).
            # of=Station scopes the lock to just Station - otherwise the join also puts
            # ChargingPort under FOR SHARE, which gets upgraded to FOR UPDATE two lines
            # down (a SHARE -> UPDATE lock upgrade is a deadlock vector under contention).
            db.query(Station).with_for_update(read=True, of=Station).join(ChargingPort).filter(
                ChargingPort.port_id == optimistic.offered_port_id
            ).first()
            # Tier 2: CHARGING_PORTS
            port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == optimistic.offered_port_id).first()
            # Tier 3: USERS
            user = db.query(User).with_for_update().filter(User.user_id == optimistic.user_id).first()
            # Tier 3.5: WAITLIST
            entry = db.query(Waitlist).with_for_update().filter(Waitlist.waitlist_id == waitlist_id).first()

            if not entry or not port or not user:
                db.rollback()
                continue
            # Re-check under lock: another request may have confirmed/left in the meantime.
            if entry.offered_at is None or entry.offered_at > cutoff:
                db.rollback()
                continue

            db.delete(entry)
            candidate = WaitlistService.find_candidate_waitlist_entry(db, port.station_id, port.connector_type, port.port_id)
            WaitlistService.apply_promotion_or_release(db, port, candidate)

            # FR-21: ignoring a waitlist offer costs 1 penalty point.
            PenaltyService.assign_penalty_point(db, user, "Ignored Waitlist Offer")

            log_audit_event(
                db,
                user_id=entry.user_id,
                action="Waitlist Offer Expired",
                entity_type="WAITLIST",
                entity_id=entry.waitlist_id,
                details={"port_id": str(port.port_id)},
                ip_address="system",
                commit=False,
            )
            db.commit()
            expired_count += 1

        return expired_count

    # ------------------------------------------------------------------
    # Background worker entry point (FR-21: async ban-triggered clearance)
    # ------------------------------------------------------------------
    @staticmethod
    def clear_waitlist_for_banned_users(db: Session) -> int:
        """FR-21: a 24-hour ban must clear the user's own active WAITLIST
        entry, but PenaltyService.assign_penalty_point cannot do that itself -
        by the time a ban is applied it already holds a Tier 3 USERS lock,
        and locking this entry's STATIONS/CHARGING_PORTS (Tiers 1-2) after
        that would invert the global lock hierarchy and risk deadlock. This
        periodic sweep instead starts fresh (no locks held yet) for each
        banned user still holding a WAITLIST row, so it can acquire locks
        top-down in the normal order.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        stale_ids = [
            row[0]
            for row in db.query(Waitlist.waitlist_id)
            .join(User, Waitlist.user_id == User.user_id)
            .filter(User.banned_until.isnot(None), User.banned_until > now)
            .order_by(Waitlist.waitlist_id.asc())
            .all()
        ]

        cleared = 0
        for waitlist_id in stale_ids:
            optimistic = db.query(Waitlist).filter(Waitlist.waitlist_id == waitlist_id).first()
            if not optimistic:
                continue

            # Tier 1: STATIONS FOR SHARE (read-only validation, no station-wide change)
            db.query(Station).with_for_update(read=True, of=Station).filter(
                Station.station_id == optimistic.station_id
            ).first()
            # Tier 2: CHARGING_PORTS (only if this entry currently holds an offer)
            port = None
            if optimistic.offered_port_id:
                port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == optimistic.offered_port_id).first()
            # Tier 3: USERS
            user = db.query(User).with_for_update().filter(User.user_id == optimistic.user_id).first()
            # Tier 3.5: WAITLIST
            entry = db.query(Waitlist).with_for_update().filter(Waitlist.waitlist_id == waitlist_id).first()

            if not entry or not user:
                db.rollback()
                continue
            # Re-check under lock: the ban may have been lifted, or the entry already left, meanwhile.
            if not user.banned_until or user.banned_until <= now:
                db.rollback()
                continue
            # Re-check under lock: if an offer was concurrently assigned (or
            # cleared) since the optimistic read that decided whether to lock a
            # CHARGING_PORTS row, `port` no longer reflects the entry's actual
            # offer state. Rolling back and letting the next sweep pick this
            # entry back up avoids deleting it without promoting/releasing the
            # port it now actually holds an offer on.
            if entry.offered_port_id != optimistic.offered_port_id:
                db.rollback()
                continue

            db.delete(entry)
            if port is not None and port.status == "Pending Waitlist":
                candidate = WaitlistService.find_candidate_waitlist_entry(db, entry.station_id, port.connector_type, port.port_id)
                WaitlistService.apply_promotion_or_release(db, port, candidate)

            log_audit_event(
                db,
                user_id=entry.user_id,
                action="Waitlist Entry Removed (Ban)",
                entity_type="WAITLIST",
                entity_id=entry.waitlist_id,
                details={"station_id": str(entry.station_id), "banned_until": user.banned_until.isoformat()},
                ip_address="system",
                commit=False,
            )
            db.commit()
            cleared += 1

        return cleared
