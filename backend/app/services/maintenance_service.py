from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.maintenance import MaintenanceSchedule
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.models.transient import Waitlist, WaitlistRejection
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import WalletTransaction
from app.schemas.maintenance_schema import MaintenanceScheduleCreate
from app.services.audit_service import log_audit_event
from app.services.notification_service import create_notification
from app.services.station_service import StationService
from app.services.waitlist_service import WaitlistService

ESCROW_AMOUNT = Decimal("1000.00")


class MaintenanceService:
    @staticmethod
    def _reoffer_stranded_waitlist_entry(db: Session, entry: Waitlist, connector_type: str) -> None:
        """FR-27: a driver whose offer was cancelled by immediate maintenance is
        never penalized - their offer is nulled out (returning them to the
        front of the queue) and, if another Available port exists at the
        station for their connector type, they are immediately re-offered
        that port instead of waiting for the next promotion cycle."""
        entry.offered_port_id = None
        entry.offered_at = None

        other_port = (
            db.query(ChargingPort)
            .filter(
                ChargingPort.station_id == entry.station_id,
                ChargingPort.connector_type == connector_type,
                ChargingPort.status == "Available",
                ChargingPort.is_active.is_(True),
            )
            .with_for_update()
            .first()
        )
        if other_port:
            WaitlistService.apply_promotion_or_release(db, other_port, entry)

    @staticmethod
    def _cancel_reservation_for_maintenance(db: Session, port: ChargingPort, ip_address: str) -> None:
        # Optimistic read first: locking RESERVATIONS (Tier 4) before USERS
        # (Tier 3) would invert the global lock hierarchy, since the
        # WalletTransaction insert below fires trg_update_wallet_balance,
        # which itself issues an UPDATE USERS and so implicitly locks that
        # row - it must already be held under FOR UPDATE by then, exactly
        # like sp_CreateReservation's own USERS -> RESERVATIONS order.
        reservation_opt = (
            db.query(Reservation)
            .filter(Reservation.port_id == port.port_id, Reservation.status == "Confirmed")
            .first()
        )
        if not reservation_opt:
            return

        # Tier 3: USERS FOR UPDATE -> Tier 4: RESERVATIONS FOR UPDATE.
        db.query(User).with_for_update().filter(User.user_id == reservation_opt.user_id).first()
        reservation = (
            db.query(Reservation)
            .with_for_update()
            .filter(Reservation.reservation_id == reservation_opt.reservation_id)
            .first()
        )
        if not reservation or reservation.status != "Confirmed":
            return

        reservation.status = "Cancelled"
        reservation.cancellation_reason = "Maintenance"
        reservation.status_updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        # FR-27: cancelled without penalty - the full escrow is refunded.
        db.add(
            WalletTransaction(
                user_id=reservation.user_id,
                amount=ESCROW_AMOUNT,
                transaction_type="Escrow Release",
                reference_id=reservation.reservation_id,
            )
        )
        create_notification(
            db,
            reservation.user_id,
            "Reservation cancelled for maintenance",
            "Your reservation was cancelled because the station scheduled urgent maintenance on this port. Your escrow has been fully refunded.",
            commit=False,
        )
        log_audit_event(
            db,
            user_id=reservation.user_id,
            action="Reservation Cancelled",
            entity_type="RESERVATIONS",
            entity_id=reservation.reservation_id,
            details={"reason": "Maintenance"},
            ip_address=ip_address,
            commit=False,
        )

    @staticmethod
    def _cancel_waitlist_offer_for_maintenance(db: Session, port: ChargingPort, ip_address: str) -> None:
        entry = db.query(Waitlist).filter(Waitlist.offered_port_id == port.port_id).with_for_update().first()
        if not entry:
            return

        MaintenanceService._reoffer_stranded_waitlist_entry(db, entry, port.connector_type)
        create_notification(
            db,
            entry.user_id,
            "Waitlist offer cancelled for maintenance",
            "Your waitlist offer was cancelled because the station scheduled urgent maintenance on this port. You have not been penalized and remain at the front of the queue.",
            commit=False,
        )
        log_audit_event(
            db,
            user_id=entry.user_id,
            action="Waitlist Offer Cancelled",
            entity_type="WAITLIST",
            entity_id=entry.waitlist_id,
            details={"reason": "Maintenance", "port_id": str(port.port_id)},
            ip_address=ip_address,
            commit=False,
        )

    @staticmethod
    def _terminate_session_for_maintenance(db: Session, port: ChargingPort, station: Station, ip_address: str) -> None:
        from app.services.session_service import SessionService  # local import: avoids a service-to-service import cycle

        # Optimistic read first, purely to discover the reservation/session
        # IDs - no locks yet.
        reservation_opt = (
            db.query(Reservation)
            .filter(Reservation.port_id == port.port_id, Reservation.status == "Active")
            .first()
        )
        if not reservation_opt:
            return
        session_opt = (
            db.query(ChargingSession)
            .filter(ChargingSession.reservation_id == reservation_opt.reservation_id, ChargingSession.end_time.is_(None))
            .first()
        )
        if not session_opt:
            return

        # Lock hierarchy (STATIONS/CHARGING_PORTS already held by the caller):
        # Tier 2.5 VEHICLES FOR SHARE -> Tier 3 USERS FOR UPDATE -> Tier 4
        # RESERVATIONS FOR UPDATE -> Tier 6 CHARGING_SESSIONS FOR UPDATE,
        # matching SessionService.stop_session's own lock order exactly.
        vehicle = db.query(Vehicle).with_for_update(read=True).filter(Vehicle.vehicle_id == reservation_opt.vehicle_id).first()
        user = db.query(User).with_for_update().filter(User.user_id == reservation_opt.user_id).first()
        reservation = (
            db.query(Reservation)
            .with_for_update()
            .filter(Reservation.reservation_id == reservation_opt.reservation_id)
            .first()
        )
        session = (
            db.query(ChargingSession)
            .with_for_update()
            .filter(ChargingSession.session_id == session_opt.session_id)
            .first()
        )

        # Re-validate under lock: another request may have changed things
        # (e.g. the driver stopped the session themselves) since the
        # optimistic read above.
        if not reservation or reservation.status != "Active" or not session or session.end_time is not None:
            return

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        SessionService._settle_and_finalize(
            db,
            session,
            reservation,
            vehicle,
            port,
            station,
            user,
            now,
            force_port_status="Maintenance",
            waive_minimum_fee=True,
            ip_address=ip_address,
            notify=False,
        )
        create_notification(
            db,
            user.user_id,
            "Charging session ended for maintenance",
            "Your charging session was ended because the station scheduled urgent maintenance on this port. The minimum session fee was waived and you were billed only for the energy actually delivered.",
            commit=False,
        )

    @staticmethod
    def _apply_immediate_maintenance(db: Session, port: ChargingPort, station: Station, ip_address: str) -> None:
        if port.status == "Reserved":
            MaintenanceService._cancel_reservation_for_maintenance(db, port, ip_address)
        elif port.status == "Pending Waitlist":
            MaintenanceService._cancel_waitlist_offer_for_maintenance(db, port, ip_address)
        elif port.status == "Charging":
            MaintenanceService._terminate_session_for_maintenance(db, port, station, ip_address)

        if port.status != "Maintenance":
            port.status = "Maintenance"
        port.is_pending_maintenance = False

    @staticmethod
    def schedule_maintenance(db: Session, current_user: User, payload: MaintenanceScheduleCreate, ip_address: str) -> MaintenanceSchedule:
        # Every other timestamp in this schema is naive UTC (Architecture.md:
        # "all times are UTC"); the frontend sends a timezone-aware ISO string
        # (toISOString()), so normalize it the same way before comparing
        # against or storing alongside naive `datetime.now(timezone.utc)` values -
        # comparing aware and naive datetimes directly raises TypeError.
        start_time = payload.start_time.astimezone(timezone.utc).replace(tzinfo=None) if payload.start_time.tzinfo else payload.start_time
        end_time = payload.end_time.astimezone(timezone.utc).replace(tzinfo=None) if payload.end_time.tzinfo else payload.end_time

        if end_time <= start_time:
            raise HTTPException(status_code=400, detail="end_time must be after start_time")

        port = db.query(ChargingPort).filter(ChargingPort.port_id == payload.port_id).first()
        if not port:
            raise HTTPException(status_code=404, detail="Port not found")
        station = db.query(Station).filter(Station.station_id == port.station_id).first()
        StationService._check_operator_permission(db, str(current_user.user_id), str(station.company_id))

        # Tier 1 -> Tier 2 lock order before touching port/reservation/waitlist/session state.
        db.query(Station).with_for_update(read=True, of=Station).filter(Station.station_id == station.station_id).first()
        port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == payload.port_id).first()

        # A port may only have one unresolved maintenance cycle at a time -
        # otherwise two "Active" rows can coexist for the same port, and once
        # the first one's expiry releases the port, the second's own expiry
        # finds the port no longer in Maintenance and is permanently skipped,
        # leaving it stuck at "Active" forever.
        unresolved = (
            db.query(MaintenanceSchedule)
            .filter(MaintenanceSchedule.port_id == port.port_id, MaintenanceSchedule.status.in_(["Scheduled", "Active"]))
            .first()
        )
        if unresolved:
            raise HTTPException(status_code=409, detail="This port already has an unresolved maintenance schedule")

        schedule = MaintenanceSchedule(port_id=port.port_id, start_time=start_time, end_time=end_time, status="Scheduled")
        db.add(schedule)
        db.flush()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        if start_time <= now:
            MaintenanceService._apply_immediate_maintenance(db, port, station, ip_address)
            schedule.status = "Active"
        elif port.status == "Charging":
            # FR-27: soft-freeze - block new reservations, but let the
            # in-progress session finish naturally; _settle_and_finalize routes
            # it into Maintenance (instead of Available/waitlist) when it ends.
            port.is_pending_maintenance = True

        log_audit_event(
            db,
            user_id=current_user.user_id,
            action="Maintenance Scheduled",
            entity_type="MAINTENANCE_SCHEDULES",
            entity_id=schedule.maintenance_id,
            details={"port_id": str(port.port_id), "start_time": start_time.isoformat(), "end_time": end_time.isoformat(), "immediate": start_time <= now},
            ip_address=ip_address,
            commit=False,
        )
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def list_schedules_for_station(db: Session, current_user: User, station_id: UUID):
        station = db.query(Station).filter(Station.station_id == station_id).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")
        StationService._check_operator_permission(db, str(current_user.user_id), str(station.company_id))

        return (
            db.query(MaintenanceSchedule)
            .join(ChargingPort, MaintenanceSchedule.port_id == ChargingPort.port_id)
            .filter(ChargingPort.station_id == station_id)
            .order_by(MaintenanceSchedule.start_time.desc())
            .all()
        )

    @staticmethod
    def _release_port_from_maintenance(db: Session, schedule: MaintenanceSchedule, port: ChargingPort, user_id, ip_address: str) -> None:
        """DD-17 recovery, shared by the manual 'Clear Bay' action and the
        automatic end_time expiry: reset the port to Available, reset the
        port's WAITLIST_REJECTIONS reputation, and decide the queue while the
        caller holds the station/port locks."""
        candidate = WaitlistService.find_candidate_waitlist_entry(db, port.station_id, port.connector_type, port.port_id)
        WaitlistService.apply_promotion_or_release(db, port, candidate)

        db.query(WaitlistRejection).filter(WaitlistRejection.port_id == port.port_id).delete()

        schedule.status = "Completed"

        log_audit_event(
            db,
            user_id=user_id,
            action="Maintenance Completed",
            entity_type="MAINTENANCE_SCHEDULES",
            entity_id=schedule.maintenance_id,
            details={"port_id": str(port.port_id)},
            ip_address=ip_address,
            commit=False,
        )

    @staticmethod
    def complete_maintenance(db: Session, current_user: User, maintenance_id: UUID, ip_address: str) -> MaintenanceSchedule:
        """Operator 'Clear Bay' action: end a Maintenance window early."""
        schedule = db.query(MaintenanceSchedule).filter(MaintenanceSchedule.maintenance_id == maintenance_id).first()
        if not schedule:
            raise HTTPException(status_code=404, detail="Maintenance schedule not found")
        port = db.query(ChargingPort).filter(ChargingPort.port_id == schedule.port_id).first()
        if not port:
            raise HTTPException(status_code=404, detail="Port not found")
        station = db.query(Station).filter(Station.station_id == port.station_id).first()
        StationService._check_operator_permission(db, str(current_user.user_id), str(station.company_id))

        if port.status != "Maintenance":
            raise HTTPException(status_code=409, detail="Port is not currently in Maintenance")

        db.query(Station).with_for_update(read=True, of=Station).filter(Station.station_id == station.station_id).first()
        port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == schedule.port_id).first()
        if port.status != "Maintenance":
            raise HTTPException(status_code=409, detail="Port is not currently in Maintenance")

        MaintenanceService._release_port_from_maintenance(db, schedule, port, current_user.user_id, ip_address)
        db.commit()
        db.refresh(schedule)
        return schedule

    @staticmethod
    def _auto_expire_finished_maintenance(db: Session) -> int:
        """Companion half of the Scheduled Maintenance Trigger: once an Active
        window's end_time has passed, automatically release the port back to
        Available (DD-17) rather than leaving it stuck in Maintenance until an
        operator manually clears it."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        due_ids = [
            row[0]
            for row in db.query(MaintenanceSchedule.maintenance_id)
            .filter(MaintenanceSchedule.status == "Active", MaintenanceSchedule.end_time <= now)
            .order_by(MaintenanceSchedule.port_id.asc())
            .all()
        ]

        expired = 0
        for maintenance_id in due_ids:
            optimistic = db.query(MaintenanceSchedule).filter(MaintenanceSchedule.maintenance_id == maintenance_id).first()
            if not optimistic or optimistic.status != "Active" or optimistic.end_time > now:
                continue

            # Tier 1: STATIONS FOR SHARE, Tier 2: CHARGING_PORTS FOR UPDATE.
            db.query(Station).join(ChargingPort).with_for_update(read=True, of=Station).filter(
                ChargingPort.port_id == optimistic.port_id
            ).first()
            port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == optimistic.port_id).first()
            schedule = db.query(MaintenanceSchedule).filter(MaintenanceSchedule.maintenance_id == maintenance_id).first()

            if not port or not schedule or schedule.status != "Active" or schedule.end_time > now:
                db.rollback()
                continue
            if port.status != "Maintenance":
                # An operator already cleared it manually, or something else
                # moved the port on - nothing left for expiry to do here.
                db.rollback()
                continue

            MaintenanceService._release_port_from_maintenance(db, schedule, port, user_id=None, ip_address="system")
            db.commit()
            expired += 1

        return expired

    @staticmethod
    def check_scheduled_maintenance(db: Session) -> int:
        """FR-27 / Architecture.md 3.4 'Scheduled Maintenance Trigger': every
        minute, transition ports whose maintenance start_time has arrived, and
        release ports whose maintenance end_time has passed. Charging ports
        are skipped in the start_time half - they were already soft-frozen
        (is_pending_maintenance=True) when scheduled, and _settle_and_finalize
        routes them into Maintenance itself once their session ends."""
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        due_ids = [
            row[0]
            for row in db.query(MaintenanceSchedule.maintenance_id)
            .filter(MaintenanceSchedule.status == "Scheduled", MaintenanceSchedule.start_time <= now)
            .order_by(MaintenanceSchedule.port_id.asc())
            .all()
        ]

        triggered = 0
        for maintenance_id in due_ids:
            optimistic = db.query(MaintenanceSchedule).filter(MaintenanceSchedule.maintenance_id == maintenance_id).first()
            if not optimistic or optimistic.status != "Scheduled" or optimistic.start_time > now:
                continue

            # Tier 1: STATIONS FOR SHARE, Tier 2: CHARGING_PORTS FOR UPDATE.
            db.query(Station).join(ChargingPort).with_for_update(read=True, of=Station).filter(
                ChargingPort.port_id == optimistic.port_id
            ).first()
            port = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == optimistic.port_id).first()
            schedule = db.query(MaintenanceSchedule).filter(MaintenanceSchedule.maintenance_id == maintenance_id).first()

            if not port or not schedule or schedule.status != "Scheduled" or schedule.start_time > now:
                db.rollback()
                continue

            station = db.query(Station).filter(Station.station_id == port.station_id).first()

            if port.status == "Charging":
                port.is_pending_maintenance = True
                db.commit()
                continue

            if port.status in ("Maintenance", "Offline"):
                db.rollback()
                continue

            MaintenanceService._apply_immediate_maintenance(db, port, station, ip_address="system")
            schedule.status = "Active"

            log_audit_event(
                db,
                user_id=None,
                action="Maintenance Triggered",
                entity_type="MAINTENANCE_SCHEDULES",
                entity_id=schedule.maintenance_id,
                details={"port_id": str(port.port_id)},
                ip_address="system",
                commit=False,
            )
            db.commit()
            triggered += 1

        return triggered + MaintenanceService._auto_expire_finished_maintenance(db)
