from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.invoice import Invoice
from app.models.maintenance import MaintenanceSchedule
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import WalletTransaction
from app.services.audit_service import log_audit_event
from app.services.notification_service import create_notification
from app.services.penalty_service import PenaltyService
from app.services.waitlist_service import WaitlistService

ESCROW_AMOUNT = Decimal("1000.00")
SLA_GRACE_PERIOD_MINUTES = 15
IDLE_GRACE_MINUTES = 30
IDLE_FEE_PER_MINUTE = Decimal("10.00")
IDLE_FEE_CAP_MINUTES = 100  # INR 1000 cap / 10 INR per min
IDLE_FEE_CAP = IDLE_FEE_PER_MINUTE * IDLE_FEE_CAP_MINUTES
BLOCKAGE_FEE_PER_HOUR = Decimal("500.00")
AUTO_TERMINATION_HOURS = 24
ABANDONMENT_PENALTY = Decimal("5000.00")

# DD-05: no numeric port kW rating exists in the schema yet, only a free-text
# charger_type. Approximate real-world power bands from that string so the
# non-linear simulation has something concrete to work with. Values match the
# operator port form's actual options plus the older seed-data strings.
CHARGER_TYPE_KW = {
    "ac level 2": 7.4,
    "level 2": 7.4,
    "dc fast": 50.0,
    "fast": 50.0,
    "ultra fast dc": 150.0,
    "ultra-fast": 150.0,
    "dcfc": 100.0,
}
DEFAULT_PORT_KW = 22.0

TWO_PLACES = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def port_power_kw(charger_type: Optional[str]) -> Decimal:
    return Decimal(str(CHARGER_TYPE_KW.get((charger_type or "").strip().lower(), DEFAULT_PORT_KW)))


def _charge_rates_pct_per_minute(battery_capacity_kwh: Decimal, power_kw: Decimal) -> tuple:
    """DD-05: full port power below 80% SoC, throttled to 20% of that power from 80-100%."""
    full_rate = (power_kw / battery_capacity_kwh) * (Decimal("100") / Decimal("60"))
    throttled_rate = full_rate * Decimal("0.2")
    return full_rate, throttled_rate


def minutes_to_reach_target(initial_pct: Decimal, target_pct: Decimal, battery_capacity_kwh: Decimal, power_kw: Decimal) -> Decimal:
    full_rate, throttled_rate = _charge_rates_pct_per_minute(battery_capacity_kwh, power_kw)
    segment1_end = min(target_pct, Decimal("80"))
    minutes = Decimal("0")
    if initial_pct < segment1_end and full_rate > 0:
        minutes += (segment1_end - initial_pct) / full_rate
    if target_pct > segment1_end and throttled_rate > 0:
        # max(initial_pct, segment1_end): if initial_pct is already above 80%
        # (e.g. 85), the throttled segment starts from there, not from 80 -
        # using segment1_end unconditionally would overcount the distance to
        # cover by (initial_pct - 80).
        minutes += (target_pct - max(initial_pct, segment1_end)) / throttled_rate
    return minutes


def current_battery_percentage(initial_pct: Decimal, target_pct: Decimal, battery_capacity_kwh: Decimal, power_kw: Decimal, elapsed_minutes: Decimal) -> Decimal:
    if elapsed_minutes <= 0:
        return initial_pct
    total_minutes = minutes_to_reach_target(initial_pct, target_pct, battery_capacity_kwh, power_kw)
    if elapsed_minutes >= total_minutes:
        return target_pct

    full_rate, throttled_rate = _charge_rates_pct_per_minute(battery_capacity_kwh, power_kw)
    segment1_end = min(target_pct, Decimal("80"))
    remaining = elapsed_minutes
    pct = initial_pct
    if pct < segment1_end and full_rate > 0:
        segment_minutes = (segment1_end - pct) / full_rate
        if remaining <= segment_minutes:
            return pct + remaining * full_rate
        remaining -= segment_minutes
        pct = segment1_end
    if pct < target_pct and throttled_rate > 0:
        pct = min(target_pct, pct + remaining * throttled_rate)
    return pct


def billable_idle_minutes(minutes_since_target_reached: Decimal) -> Decimal:
    return max(Decimal("0"), minutes_since_target_reached - Decimal(IDLE_GRACE_MINUTES))


def calculate_idle_fee(idle_minutes: Decimal) -> Decimal:
    """DD-06: INR 10/min after a 30-minute grace period, capped at INR 1,000,
    then an uncapped INR 500/hour blockage fee beyond the cap."""
    if idle_minutes <= 0:
        return Decimal("0.00")
    if idle_minutes <= IDLE_FEE_CAP_MINUTES:
        return _money(idle_minutes * IDLE_FEE_PER_MINUTE)
    extra_hours = (idle_minutes - IDLE_FEE_CAP_MINUTES) / Decimal("60")
    return _money(IDLE_FEE_CAP + extra_hours * BLOCKAGE_FEE_PER_HOUR)


def compute_secondary_hold(session: ChargingSession, vehicle: Vehicle, station: Station) -> Decimal:
    """The energy pre-authorization taken at session start (DD-20). Deterministic
    from immutable session/vehicle/station fields, so it's recomputed here rather
    than stored, matching sp_StartSession's v_secondary_cost formula exactly."""
    energy_pct = Decimal(str(session.target_battery_percentage)) - Decimal(str(session.initial_battery_percentage))
    return max(
        Decimal(str(station.minimum_session_fee)),
        _money(energy_pct / Decimal("100") * Decimal(str(vehicle.battery_capacity)) * Decimal(str(session.applied_tariff))),
    )


def compute_snapshot(session: ChargingSession, vehicle: Vehicle, port: ChargingPort, station: Station, at_time: datetime) -> dict:
    """Live (poll) or final (stop/auto-terminate) snapshot of a session's
    progress, energy delivered, and cost so far. `at_time` lets callers cap
    the calculation at an exact moment (e.g. the 24-hour auto-termination
    boundary) rather than always using "now"."""
    elapsed_minutes = Decimal((at_time - session.start_time).total_seconds()) / Decimal("60")
    if elapsed_minutes < 0:
        elapsed_minutes = Decimal("0")

    power_kw = port_power_kw(port.charger_type)
    battery_capacity = Decimal(str(vehicle.battery_capacity))
    initial_pct = Decimal(str(session.initial_battery_percentage))
    target_pct = Decimal(str(session.target_battery_percentage))
    tariff = Decimal(str(session.applied_tariff))

    minutes_to_target = minutes_to_reach_target(initial_pct, target_pct, battery_capacity, power_kw)
    current_pct = current_battery_percentage(initial_pct, target_pct, battery_capacity, power_kw, elapsed_minutes)
    minutes_since_target = max(Decimal("0"), elapsed_minutes - minutes_to_target)
    idle_minutes = billable_idle_minutes(minutes_since_target)
    idle_fee = calculate_idle_fee(idle_minutes)

    energy_delivered_pct = current_pct - initial_pct
    energy_kwh = _money(energy_delivered_pct / Decimal("100") * battery_capacity)
    energy_cost = _money(energy_kwh * tariff)
    energy_charge = max(energy_cost, Decimal(str(station.minimum_session_fee)))
    total_cost = _money(energy_charge + idle_fee)

    return {
        "current_battery_percentage": current_pct,
        "target_reached": current_pct >= target_pct,
        "energy_delivered_kwh": energy_kwh,
        "energy_cost": energy_charge,
        "idle_minutes": idle_minutes,
        "idle_fee": idle_fee,
        "total_cost": total_cost,
        "elapsed_minutes": elapsed_minutes,
        "eta_minutes_remaining": max(Decimal("0"), minutes_to_target - elapsed_minutes),
    }


class SessionService:
    @staticmethod
    def start_session(
        db: Session,
        current_user: User,
        reservation_id: UUID,
        initial_pct: Decimal,
        target_pct: Decimal,
        ip_address: str,
        qr_code: str = "",
        latitude: Optional[Decimal] = None,
        longitude: Optional[Decimal] = None,
    ) -> ChargingSession:
        # FR-14: QR token and GPS proximity validation
        if qr_code:
            reservation_pre = db.query(Reservation).filter(
                Reservation.reservation_id == reservation_id
            ).first()
            if reservation_pre:
                port = db.query(ChargingPort).filter(
                    ChargingPort.port_id == reservation_pre.port_id
                ).first()
                if port:
                    # Validate QR token matches the port's stable token
                    if str(port.qr_token) != qr_code and port.qr_code != qr_code:
                        raise HTTPException(
                            status_code=400,
                            detail="QR code does not match this charging port. Please scan the correct port."
                        )
                    # GPS proximity check — must be within 200m
                    if latitude is not None and longitude is not None:
                        result = db.execute(
                            text("""
                                SELECT ST_DWithin(
                                    gps_coordinates,
                                    ST_MakePoint(:lon, :lat)::geography,
                                    200
                                )
                                FROM stations
                                WHERE station_id = :station_id
                            """),
                            {"lat": float(latitude), "lon": float(longitude), "station_id": str(port.station_id)},
                        ).scalar()
                        if result is False:
                            raise HTTPException(
                                status_code=400,
                                detail="You must be within 200m of the station to start a charging session."
                            )
        try:
            db.execute(
                text("""
                    CALL sp_StartSession(:p_user_id, :p_reservation_id, :p_initial, :p_target)
                """),
                {
                    "p_user_id": current_user.user_id,
                    "p_reservation_id": reservation_id,
                    "p_initial": initial_pct,
                    "p_target": target_pct,
                },
            )
            db.commit()
        except Exception as e:
            db.rollback()
            error_msg = str(e)
            if "402" in error_msg or "Insufficient funds" in error_msg:
                raise HTTPException(status_code=402, detail="Insufficient funds for the energy pre-authorization")
            elif "not Confirmed" in error_msg:
                raise HTTPException(status_code=400, detail="Reservation is not in a Confirmed state")
            elif "IDOR check failed" in error_msg:
                raise HTTPException(status_code=403, detail="This reservation does not belong to you")
            elif "suspended" in error_msg:
                raise HTTPException(status_code=403, detail="Account is suspended pending unpaid invoices")
            elif "unpaid invoices" in error_msg:
                raise HTTPException(status_code=402, detail="You have unpaid invoices; settle them before starting a session")
            elif "pending maintenance" in error_msg:
                raise HTTPException(status_code=409, detail="This port is pending maintenance and cannot start a new session")
            elif "not Reserved" in error_msg:
                raise HTTPException(status_code=409, detail="Port is not in a Reserved state")
            elif "Insufficient time available" in error_msg:
                raise HTTPException(status_code=400, detail="Not enough time remains before the station closes or scheduled maintenance begins")
            else:
                raise HTTPException(status_code=400, detail=error_msg.split("\n")[0])

        session = (
            db.query(ChargingSession)
            .filter(ChargingSession.reservation_id == reservation_id)
            .order_by(ChargingSession.created_at.desc())
            .first()
        )
        if not session:
            raise HTTPException(status_code=500, detail="Failed to retrieve created session")

        # FR-15: Set hardware handshake deadline — billing doesn't begin until ack arrives
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        session.hardware_acked = False
        session.hardware_ack_deadline = now + timedelta(seconds=60)
        db.commit()

        log_audit_event(
            db,
            user_id=current_user.user_id,
            action="Charging Session Started",
            entity_type="CHARGING_SESSIONS",
            entity_id=session.session_id,
            details={"reservation_id": str(reservation_id)},
            ip_address=str(ip_address),
        )
        return session


    @staticmethod
    def _load_active_session_context(db: Session, current_user: User):
        session = (
            db.query(ChargingSession)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .filter(Reservation.user_id == current_user.user_id, ChargingSession.end_time.is_(None))
            .first()
        )
        if not session:
            return None, None, None, None, None
        reservation = db.query(Reservation).filter(Reservation.reservation_id == session.reservation_id).first()
        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == reservation.vehicle_id).first()
        port = db.query(ChargingPort).filter(ChargingPort.port_id == reservation.port_id).first()
        station = db.query(Station).filter(Station.station_id == port.station_id).first()
        return session, reservation, vehicle, port, station

    @staticmethod
    def get_active_session_status(db: Session, current_user: User) -> Optional[dict]:
        session, reservation, vehicle, port, station = SessionService._load_active_session_context(db, current_user)
        if not session:
            return None
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        snapshot = compute_snapshot(session, vehicle, port, station, now)
        return {
            "session_id": session.session_id,
            "reservation_id": session.reservation_id,
            "port_id": port.port_id,
            "vehicle_id": vehicle.vehicle_id,
            "initial_battery_percentage": session.initial_battery_percentage,
            "target_battery_percentage": session.target_battery_percentage,
            "applied_tariff": session.applied_tariff,
            "start_time": session.start_time,
            **snapshot,
        }

    @staticmethod
    def _settle_and_finalize(
        db: Session,
        session: ChargingSession,
        reservation: Reservation,
        vehicle: Vehicle,
        port: ChargingPort,
        station: Station,
        user: User,
        at_time: datetime,
        extra_penalty: Decimal = Decimal("0.00"),
        port_goes_offline: bool = False,
        ip_address: str = "system",
        waive_minimum_fee: bool = False,
        force_port_status: Optional[str] = None,
        notify: bool = True,
    ) -> Invoice:
        """DD-10 Session Termination Service, shared by manual stop, the
        24-hour auto-termination worker, and (via force_port_status /
        waive_minimum_fee) FR-27's immediate-maintenance forced termination.
        Caller must already hold STATIONS FOR SHARE -> CHARGING_PORTS FOR
        UPDATE -> VEHICLES FOR SHARE -> USERS FOR UPDATE -> RESERVATIONS FOR
        UPDATE -> CHARGING_SESSIONS FOR UPDATE.

        waive_minimum_fee=True bills strictly the raw energy cost (no
        minimum_session_fee floor, no idle fee) per FR-27 - maintenance is not
        the driver's fault, so neither the minimum-fee floor nor an idle
        penalty should apply to a session cut short for it.

        force_port_status, when set, skips both the "Offline" and waitlist-
        promotion branches below and assigns the port that status directly
        (used to send it straight to "Maintenance" instead of back into the
        waitlist rotation).

        notify=False suppresses the generic "Charging completion" / "Invoice
        generation" notifications below - callers with a more specific message
        for this exact termination (e.g. MaintenanceService's forced stop)
        send their own instead, to avoid double-notifying the driver.

        USERS.wallet_balance is a derived cache maintained by the DB trigger
        trg_update_wallet_balance as SUM(WALLET_TRANSACTIONS) for the user - it
        is never written directly here. Each ledger row below is what actually
        moves the balance; settlement_delta and projected_balance are only used
        locally to decide is_paid/is_suspended before the trigger applies the
        real change.

        is_paid is deliberately based on the user's overall pooled balance
        after this settlement, not on whether this session's own escrow +
        energy pre-auth happened to cover its bill: the wallet has a single
        balance, not per-session earmarks, so a driver with healthy overall
        funds shouldn't be suspended just because one session's idle fee
        outgrew what was pre-authorized specifically for it.
        """
        snapshot = compute_snapshot(session, vehicle, port, station, at_time)
        session_cost = snapshot["energy_cost"] if waive_minimum_fee else snapshot["total_cost"]
        total_due = _money(session_cost + extra_penalty)

        secondary_hold = compute_secondary_hold(session, vehicle, station)
        available_preauth = ESCROW_AMOUNT + secondary_hold
        settlement_delta = available_preauth - total_due  # positive = refund, negative = shortfall
        projected_balance = _money(user.wallet_balance + settlement_delta)

        is_paid = projected_balance >= 0
        if not is_paid:
            user.is_suspended = True

        session.end_time = at_time

        invoice = Invoice(
            charging_session_id=session.session_id,
            user_id=user.user_id,
            total_amount=total_due,
            is_paid=is_paid,
            paid_at=at_time if is_paid else None,
        )
        db.add(invoice)
        db.flush()

        # Split into two ledger legs so abandonment penalties stay independently
        # auditable; they sum to the same settlement_delta computed above
        # (available_preauth - session_cost - extra_penalty == settlement_delta).
        session_settlement_amount = _money(available_preauth - session_cost)
        db.add(WalletTransaction(user_id=user.user_id, amount=session_settlement_amount, transaction_type="Session Settlement", reference_id=session.session_id))
        if extra_penalty > 0:
            db.add(WalletTransaction(user_id=user.user_id, amount=-extra_penalty, transaction_type="Abandonment Penalty", reference_id=session.session_id))

        reservation.status = "Completed"

        if force_port_status:
            port.status = force_port_status
            port.is_pending_maintenance = False
        elif port_goes_offline:
            port.status = "Offline"
        elif port.is_pending_maintenance:
            # FR-27: a maintenance window was scheduled for while this port was
            # still Charging (is_pending_maintenance=True, new reservations
            # already blocked) - now that the session has ended naturally, the
            # port goes straight to Maintenance instead of back into rotation.
            port.status = "Maintenance"
            port.is_pending_maintenance = False
            schedule = (
                db.query(MaintenanceSchedule)
                .filter(MaintenanceSchedule.port_id == port.port_id, MaintenanceSchedule.status == "Scheduled")
                .order_by(MaintenanceSchedule.start_time.asc())
                .first()
            )
            if schedule:
                schedule.status = "Active"
        else:
            candidate = WaitlistService.find_candidate_waitlist_entry(db, port.station_id, port.connector_type, port.port_id)
            WaitlistService.apply_promotion_or_release(db, port, candidate)

        log_audit_event(
            db,
            user_id=user.user_id,
            action="Charging Session Ended",
            entity_type="CHARGING_SESSIONS",
            entity_id=session.session_id,
            details={
                "total_amount": str(total_due),
                "is_paid": is_paid,
                "abandonment": extra_penalty > 0,
            },
            ip_address=str(ip_address),
            commit=False,
        )
        log_audit_event(
            db,
            user_id=user.user_id,
            action="Invoice Generated",
            entity_type="INVOICES",
            entity_id=invoice.invoice_id,
            details={"total_amount": str(total_due), "is_paid": is_paid},
            ip_address=str(ip_address),
            commit=False,
        )

        if notify:
            create_notification(db, user.user_id, "Charging session complete", "Your charging session has ended.", commit=False)
            create_notification(
                db,
                user.user_id,
                "Invoice generated",
                f"An invoice for {total_due} has been generated for your session."
                + ("" if is_paid else " Your wallet balance was insufficient to cover it in full."),
                commit=False,
            )

        return invoice

    @staticmethod
    def stop_session(db: Session, current_user: User, ip_address: str) -> Invoice:
        session, reservation, vehicle, port, station = SessionService._load_active_session_context(db, current_user)
        if not session:
            raise HTTPException(status_code=404, detail="No active charging session")

        # DD-24-style optimistic read then lock in global hierarchy order.
        db.query(Station).with_for_update(read=True, of=Station).filter(Station.station_id == station.station_id).first()
        port_locked = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == port.port_id).first()
        db.query(Vehicle).with_for_update(read=True).filter(Vehicle.vehicle_id == vehicle.vehicle_id).first()
        user = db.query(User).with_for_update().filter(User.user_id == current_user.user_id).first()
        reservation_locked = db.query(Reservation).with_for_update().filter(Reservation.reservation_id == reservation.reservation_id).first()
        session_locked = db.query(ChargingSession).with_for_update().filter(ChargingSession.session_id == session.session_id).first()

        if not session_locked or session_locked.end_time is not None:
            db.rollback()
            raise HTTPException(status_code=409, detail="Session has already ended")
        if not reservation_locked or reservation_locked.user_id != current_user.user_id:
            db.rollback()
            raise HTTPException(status_code=403, detail="This session does not belong to you")

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        invoice = SessionService._settle_and_finalize(
            db, session_locked, reservation_locked, vehicle, port_locked, station, user, now, ip_address=ip_address,
        )
        db.commit()
        return invoice

    @staticmethod
    def auto_terminate_stale_sessions(db: Session) -> int:
        """FR-16: sessions IDLE (power delivery stopped, i.e. target reached)
        for 24 accumulated hours are force-terminated - port goes Offline
        (operator intervention required, no waitlist promotion) and a 5000
        INR abandonment penalty is added to the invoice.

        "24 accumulated hours" means idle time, not total session duration -
        a vehicle that charges slowly for hours before reaching target
        shouldn't be cut off before it has actually been idle for a day. The
        SQL filter below (start_time <= 24h ago) is a safe, loose pre-filter:
        total session duration is always >= idle duration, so it can never
        exclude a session that's genuinely due, only include some that
        aren't yet (still mid-charge, or idle for less than 24h) - those are
        skipped by the precise per-candidate check once vehicle/port details
        are available to recompute how long the charge itself took.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        cutoff = now - timedelta(hours=AUTO_TERMINATION_HOURS)

        stale_ids = [
            row[0]
            for row in db.query(ChargingSession.session_id)
            .filter(ChargingSession.end_time.is_(None), ChargingSession.start_time <= cutoff)
            .order_by(ChargingSession.session_id.asc())
            .all()
        ]

        terminated = 0
        for session_id in stale_ids:
            optimistic = db.query(ChargingSession).filter(ChargingSession.session_id == session_id).first()
            if not optimistic or optimistic.end_time is not None:
                continue
            reservation = db.query(Reservation).filter(Reservation.reservation_id == optimistic.reservation_id).first()
            if not reservation:
                continue
            port = db.query(ChargingPort).filter(ChargingPort.port_id == reservation.port_id).first()
            vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == reservation.vehicle_id).first()
            station = db.query(Station).filter(Station.station_id == port.station_id).first()

            elapsed_minutes = Decimal((now - optimistic.start_time).total_seconds()) / Decimal("60")
            minutes_to_target = minutes_to_reach_target(
                Decimal(str(optimistic.initial_battery_percentage)),
                Decimal(str(optimistic.target_battery_percentage)),
                Decimal(str(vehicle.battery_capacity)),
                port_power_kw(port.charger_type),
            )
            idle_minutes_raw = elapsed_minutes - minutes_to_target
            if idle_minutes_raw < Decimal(AUTO_TERMINATION_HOURS * 60):
                continue

            db.query(Station).with_for_update(read=True, of=Station).filter(Station.station_id == station.station_id).first()
            port_locked = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == port.port_id).first()
            db.query(Vehicle).with_for_update(read=True).filter(Vehicle.vehicle_id == vehicle.vehicle_id).first()
            user = db.query(User).with_for_update().filter(User.user_id == reservation.user_id).first()
            reservation_locked = db.query(Reservation).with_for_update().filter(Reservation.reservation_id == reservation.reservation_id).first()
            session_locked = db.query(ChargingSession).with_for_update().filter(ChargingSession.session_id == session_id).first()

            if not session_locked or session_locked.end_time is not None:
                db.rollback()
                continue

            # end_time is "now" (the actual moment of forced termination), not a
            # fixed start_time + 24h: energy is already naturally capped by the
            # simulation once the target is reached, so this only affects idle
            # fees, which per DD-06 are meant to keep accruing (uncapped, in the
            # blockage tier) for exactly as long as the vehicle is genuinely idle.
            SessionService._settle_and_finalize(
                db, session_locked, reservation_locked, vehicle, port_locked, station, user, now,
                extra_penalty=ABANDONMENT_PENALTY, port_goes_offline=True, ip_address="system",
            )
            db.commit()
            terminated += 1

        return terminated

    @staticmethod
    def enforce_overstay_penalties(db: Session) -> int:
        """FR-21 'Overstay Penalty Enforcer': 1 penalty point for overstaying
        after charging is complete, i.e. once the free 30-minute grace period
        (IDLE_GRACE_MINUTES) following target_reached has elapsed. Fires
        exactly once per session via is_overstay_penalized, independently of
        the 24-hour auto-termination sweep above (a session can overstay long
        before it's anywhere near auto-termination).
        """
        candidate_ids = [
            row[0]
            for row in db.query(ChargingSession.session_id)
            .filter(ChargingSession.end_time.is_(None), ChargingSession.is_overstay_penalized.is_(False))
            .order_by(ChargingSession.session_id.asc())
            .all()
        ]

        penalized = 0
        for session_id in candidate_ids:
            optimistic = db.query(ChargingSession).filter(ChargingSession.session_id == session_id).first()
            if not optimistic or optimistic.end_time is not None or optimistic.is_overstay_penalized:
                continue
            reservation = db.query(Reservation).filter(Reservation.reservation_id == optimistic.reservation_id).first()
            if not reservation:
                continue
            port = db.query(ChargingPort).filter(ChargingPort.port_id == reservation.port_id).first()
            vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == reservation.vehicle_id).first()
            if not port or not vehicle:
                continue

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            elapsed_minutes = Decimal((now - optimistic.start_time).total_seconds()) / Decimal("60")
            minutes_to_target = minutes_to_reach_target(
                Decimal(str(optimistic.initial_battery_percentage)),
                Decimal(str(optimistic.target_battery_percentage)),
                Decimal(str(vehicle.battery_capacity)),
                port_power_kw(port.charger_type),
            )

            # Architecture.md 3.4 "Overstay Penalty Enforcer": while the station's
            # gate is currently locked, the driver is physically prevented from
            # retrieving their vehicle, so that time must not count as idle. The
            # session's own idle_start_time is never persisted elsewhere (the
            # "target reached" moment is purely derived, not an event), so it's
            # approximated here as start_time + minutes_to_target, mirroring the
            # optimistic elapsed-time calculation above.
            station_optimistic = db.query(Station).filter(Station.station_id == port.station_id).first()
            if not station_optimistic:
                continue
            closure_seconds = Decimal(optimistic.cumulative_closure_seconds or 0)
            if station_optimistic.locked_gate and station_optimistic.locked_gate_at:
                idle_start = optimistic.start_time + timedelta(minutes=float(minutes_to_target))
                active_closure = (now - max(station_optimistic.locked_gate_at, idle_start)).total_seconds()
                closure_seconds += Decimal(max(0, active_closure))

            effective_elapsed_minutes = max(Decimal("0"), elapsed_minutes - closure_seconds / Decimal("60"))
            minutes_since_target = max(Decimal("0"), effective_elapsed_minutes - minutes_to_target)
            if billable_idle_minutes(minutes_since_target) <= 0:
                continue

            # Global lock hierarchy (Architecture.md 3.5): Tier 1 STATIONS FOR
            # SHARE -> Tier 2 CHARGING_PORTS FOR SHARE -> Tier 3 USERS FOR UPDATE
            # -> Tier 6 CHARGING_SESSIONS FOR UPDATE.
            station = db.query(Station).with_for_update(read=True, of=Station).filter(Station.station_id == port.station_id).first()
            port_locked = db.query(ChargingPort).with_for_update(read=True, of=ChargingPort).filter(ChargingPort.port_id == port.port_id).first()
            user = db.query(User).with_for_update().filter(User.user_id == reservation.user_id).first()
            session_locked = db.query(ChargingSession).with_for_update().filter(ChargingSession.session_id == session_id).first()

            if (
                not station
                or not port_locked
                or not user
                or not session_locked
                or session_locked.end_time is not None
                or session_locked.is_overstay_penalized
            ):
                db.rollback()
                continue

            # Re-validate under lock: the gate may have been locked/unlocked
            # concurrently since the optimistic read above.
            closure_seconds = Decimal(session_locked.cumulative_closure_seconds or 0)
            if station.locked_gate and station.locked_gate_at:
                idle_start = session_locked.start_time + timedelta(minutes=float(minutes_to_target))
                active_closure = (now - max(station.locked_gate_at, idle_start)).total_seconds()
                closure_seconds += Decimal(max(0, active_closure))
            effective_elapsed_minutes = max(Decimal("0"), elapsed_minutes - closure_seconds / Decimal("60"))
            minutes_since_target = max(Decimal("0"), effective_elapsed_minutes - minutes_to_target)
            if billable_idle_minutes(minutes_since_target) <= 0:
                db.rollback()
                continue

            session_locked.is_overstay_penalized = True
            PenaltyService.assign_penalty_point(db, user, "Overstay After Charging Complete")
            db.commit()
            penalized += 1

        return penalized

    @staticmethod
    def challenge_port(
        db: Session,
        challenger: User,
        port_id: UUID,
        latitude: Decimal,
        longitude: Decimal,
        qr_code: str,
        vehicle_id: Optional[UUID] = None,
        ip_address: str = "unknown",
    ) -> dict:
        """FR-32: Ghost Session Resolution / Port Challenge.
        If a bay shows 'Charging' but vehicle is gone, challenger scans port QR within 200m.
        If mock hardware state is Disconnected, force-terminates ghost session billing strictly up to now,
        runs waitlist promotion, or grants challenger a 15-min reservation if no waitlist queued."""
        # Check challenger has no active session
        active_challenger_session = (
            db.query(ChargingSession.session_id)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .filter(Reservation.user_id == challenger.user_id, ChargingSession.end_time.is_(None))
            .first()
        )
        if active_challenger_session:
            raise HTTPException(status_code=400, detail="You already have an active charging session")

        # Port validation
        port = db.query(ChargingPort).filter(ChargingPort.port_id == port_id).first()
        if not port:
            raise HTTPException(status_code=404, detail="Port not found")
        if port.status == "Offline":
            raise HTTPException(status_code=400, detail="Port is offline and requires operator intervention, not a challenge")
        if port.status in ["Maintenance"]:
            raise HTTPException(status_code=400, detail="Port is currently in maintenance")
        if port.status != "Charging":
            raise HTTPException(status_code=400, detail=f"Port is currently {port.status}, not Charging")

        # Geofence check: within 200m of station
        station = db.query(Station).filter(Station.station_id == port.station_id).first()
        if not station:
            raise HTTPException(status_code=404, detail="Station not found")

        point = f"SRID=4326;POINT({longitude} {latitude})"
        distance = db.execute(
            text("SELECT ST_Distance(gps_coordinates, ST_GeogFromText(:point)) FROM stations WHERE station_id = :station_id"),
            {"point": point, "station_id": str(station.station_id)},
        ).scalar()
        if distance is None or distance > 200:
            raise HTTPException(status_code=400, detail="You must be within 200m of the station to challenge this port")

        # QR validation
        if port.qr_token and str(qr_code).strip() != str(port.qr_token):
            raise HTTPException(status_code=400, detail="Scanned QR code does not match this charging port")

        # Find active session on this port
        reservation = (
            db.query(Reservation)
            .filter(Reservation.port_id == port.port_id, Reservation.status == "Active")
            .order_by(Reservation.created_at.desc())
            .first()
        )
        if not reservation:
            raise HTTPException(status_code=400, detail="No active reservation found on this port")

        session = (
            db.query(ChargingSession)
            .filter(ChargingSession.reservation_id == reservation.reservation_id, ChargingSession.end_time.is_(None))
            .first()
        )
        if not session:
            raise HTTPException(status_code=400, detail="No active charging session found on this port")

        # Query hardware state: State A / Disconnected means physically disconnected
        hw_state = (session.hardware_state or "Disconnected").strip().lower()
        if hw_state in ["connected", "charging", "state b", "state c"]:
            raise HTTPException(status_code=400, detail="Hardware indicates vehicle is still connected. Challenge rejected.")

        # Deadlock prevention: Acquire user locks in ascending user_id order
        user_ids = sorted([str(reservation.user_id), str(challenger.user_id)])
        locked_users = (
            db.query(User)
            .filter(User.user_id.in_([UUID(u) for u in user_ids]))
            .with_for_update()
            .all()
        )
        session_user = next((u for u in locked_users if u.user_id == reservation.user_id), None)
        challenger_user = next((u for u in locked_users if u.user_id == challenger.user_id), challenger)

        vehicle = db.query(Vehicle).filter(Vehicle.vehicle_id == reservation.vehicle_id).first()
        port_locked = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == port.port_id).first()
        station_locked = db.query(Station).with_for_update(read=True, of=Station).filter(Station.station_id == port.station_id).first()
        session_locked = db.query(ChargingSession).with_for_update().filter(ChargingSession.session_id == session.session_id).first()
        reservation_locked = db.query(Reservation).with_for_update().filter(Reservation.reservation_id == reservation.reservation_id).first()

        now = datetime.now(timezone.utc).replace(tzinfo=None)

        # Terminate the ghost session billing strictly up to now
        SessionService._settle_and_finalize(
            db, session_locked, reservation_locked, vehicle, port_locked, station_locked, session_user, now,
            ip_address=ip_address,
        )

        log_audit_event(
            db,
            user_id=challenger.user_id,
            action="Port Challenge Successful",
            entity_type="CHARGING_PORTS",
            entity_id=port.port_id,
            details={"ghost_session_id": str(session.session_id), "ghost_user_id": str(reservation.user_id)},
            ip_address=str(ip_address),
            commit=False,
        )

        # Check if port was claimed by waitlist promotion
        created_res_id = None
        if port_locked.status == "Pending Waitlist":
            msg = "Ghost session terminated. The port has been offered to the next driver in the waitlist queue."
        else:
            # Challenger gets a 15-minute reservation if eligible
            challenger_veh = None
            if vehicle_id:
                challenger_veh = db.query(Vehicle).filter(
                    Vehicle.vehicle_id == vehicle_id,
                    Vehicle.user_id == challenger.user_id,
                    Vehicle.is_active.is_(True),
                ).first()
            if not challenger_veh:
                challenger_veh = db.query(Vehicle).filter(
                    Vehicle.user_id == challenger.user_id,
                    Vehicle.connector_type == port.connector_type,
                    Vehicle.is_active.is_(True),
                ).first()
            if not challenger_veh:
                challenger_veh = db.query(Vehicle).filter(
                    Vehicle.user_id == challenger.user_id,
                    Vehicle.is_active.is_(True),
                ).first()

            if challenger_veh and challenger_user.wallet_balance >= ESCROW_AMOUNT:
                try:
                    db.execute(
                        text("""
                            CALL sp_CreateReservation(
                                :p_user_id,
                                :p_port_id,
                                :p_vehicle_id,
                                :p_grace_period_minutes,
                                :p_cooldown_minutes,
                                :p_ip_address
                            )
                        """),
                        {
                            "p_user_id": challenger.user_id,
                            "p_port_id": str(port.port_id),
                            "p_vehicle_id": challenger_veh.vehicle_id,
                            "p_grace_period_minutes": 15,
                            "p_cooldown_minutes": 60,
                            "p_ip_address": str(ip_address),
                        },
                    )
                    new_res = (
                        db.query(Reservation)
                        .filter(Reservation.user_id == challenger.user_id, Reservation.port_id == port.port_id, Reservation.status == "Confirmed")
                        .order_by(Reservation.created_at.desc())
                        .first()
                    )
                    if new_res:
                        created_res_id = new_res.reservation_id
                    msg = "Ghost session terminated. You have been granted a 15-minute reservation on this port."
                except Exception:
                    port_locked.status = "Available"
                    msg = "Ghost session terminated. The port is now Available."
            else:
                port_locked.status = "Available"
                msg = "Ghost session terminated. The port is now Available for reservation."

        db.commit()
        return {
            "success": True,
            "message": msg,
            "reservation_id": created_res_id,
            "port_status": port_locked.status,
        }

