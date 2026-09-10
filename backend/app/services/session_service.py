from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.models.user import User
from app.models.vehicle import Vehicle
from app.models.wallet import WalletTransaction
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
        minutes += (target_pct - segment1_end) / throttled_rate
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
    def start_session(db: Session, current_user: User, reservation_id: str, initial_pct: Decimal, target_pct: Decimal, ip_address: str) -> ChargingSession:
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

        db.add(AuditLog(
            user_id=current_user.user_id,
            action="Charging Session Started",
            entity_type="CHARGING_SESSIONS",
            entity_id=session.session_id,
            details={"reservation_id": str(reservation_id)},
            ip_address=str(ip_address),
        ))
        db.commit()
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
    ) -> Invoice:
        """DD-10 Session Termination Service, shared by manual stop and the
        24-hour auto-termination worker. Caller must already hold STATIONS FOR
        SHARE -> CHARGING_PORTS FOR UPDATE -> VEHICLES FOR SHARE -> USERS FOR
        UPDATE -> RESERVATIONS FOR UPDATE -> CHARGING_SESSIONS FOR UPDATE.

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
        session_cost = snapshot["total_cost"]
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

        # Split into two ledger legs so abandonment penalties stay independently
        # auditable; they sum to the same settlement_delta computed above
        # (available_preauth - session_cost - extra_penalty == settlement_delta).
        session_settlement_amount = _money(available_preauth - session_cost)
        db.add(WalletTransaction(user_id=user.user_id, amount=session_settlement_amount, transaction_type="Session Settlement", reference_id=session.session_id))
        if extra_penalty > 0:
            db.add(WalletTransaction(user_id=user.user_id, amount=-extra_penalty, transaction_type="Abandonment Penalty", reference_id=session.session_id))

        reservation.status = "Completed"

        if port_goes_offline:
            port.status = "Offline"
        else:
            candidate = WaitlistService.find_candidate_waitlist_entry(db, port.station_id, port.connector_type, port.port_id)
            WaitlistService.apply_promotion_or_release(db, port, candidate)

        db.add(AuditLog(
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
        ))
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
        """FR-16: sessions idle for 24 accumulated hours are force-terminated -
        port goes Offline (operator intervention required, no waitlist
        promotion) and a 5000 INR abandonment penalty is added to the invoice."""
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=AUTO_TERMINATION_HOURS)

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

            db.query(Station).with_for_update(read=True, of=Station).filter(Station.station_id == station.station_id).first()
            port_locked = db.query(ChargingPort).with_for_update().filter(ChargingPort.port_id == port.port_id).first()
            db.query(Vehicle).with_for_update(read=True).filter(Vehicle.vehicle_id == vehicle.vehicle_id).first()
            user = db.query(User).with_for_update().filter(User.user_id == reservation.user_id).first()
            reservation_locked = db.query(Reservation).with_for_update().filter(Reservation.reservation_id == reservation.reservation_id).first()
            session_locked = db.query(ChargingSession).with_for_update().filter(ChargingSession.session_id == session_id).first()

            if not session_locked or session_locked.end_time is not None:
                db.rollback()
                continue

            end_time = session_locked.start_time + timedelta(hours=AUTO_TERMINATION_HOURS)
            SessionService._settle_and_finalize(
                db, session_locked, reservation_locked, vehicle, port_locked, station, user, end_time,
                extra_penalty=ABANDONMENT_PENALTY, port_goes_offline=True, ip_address="system",
            )
            db.commit()
            terminated += 1

        return terminated
