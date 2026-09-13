from datetime import datetime, timedelta, timezone

from sqlalchemy import Date, cast, func
from sqlalchemy.orm import Session

from app.models.audit import AuditLog
from app.models.company import Company
from app.models.invoice import Invoice
from app.models.reservation import Reservation
from app.models.session import ChargingSession
from app.models.station import ChargingPort, Station
from app.models.transient import Waitlist
from app.models.user import User

REVENUE_TREND_DAYS = 30
PEAK_HOURS_WINDOW_DAYS = 30
POPULAR_STATIONS_LIMIT = 5


def _revenue_by_day(db: Session, port_ids=None):
    """FR-23/24/25 revenue trend. DD-08: financial reporting queries are
    intentionally NOT filtered by is_active, so revenue from soft-deleted
    stations/companies is preserved in historical reports."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=REVENUE_TREND_DAYS)
    query = db.query(cast(Invoice.created_at, Date).label("day"), func.coalesce(func.sum(Invoice.total_amount), 0).label("revenue")).filter(
        Invoice.is_paid.is_(True), Invoice.created_at >= since
    )
    if port_ids is not None:
        query = (
            query.join(ChargingSession, Invoice.charging_session_id == ChargingSession.session_id)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .filter(Reservation.port_id.in_(port_ids))
        )
    rows = query.group_by("day").order_by("day").all()
    return [{"date": row.day.isoformat(), "revenue": float(row.revenue)} for row in rows]


class ReportService:
    @staticmethod
    def get_admin_report(db: Session) -> dict:
        total_users = db.query(func.count(User.user_id)).filter(User.is_active.is_(True)).scalar()
        total_companies = db.query(func.count(Company.company_id)).scalar()
        total_stations = db.query(func.count(Station.station_id)).scalar()

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        last_24h = now - timedelta(hours=24)
        system_activity_24h = db.query(func.count(AuditLog.log_id)).filter(AuditLog.created_at >= last_24h).scalar()

        top_actions_rows = (
            db.query(AuditLog.action, func.count(AuditLog.log_id).label("count"))
            .filter(AuditLog.created_at >= last_24h)
            .group_by(AuditLog.action)
            .order_by(func.count(AuditLog.log_id).desc())
            .limit(5)
            .all()
        )

        active_sessions = db.query(func.count(ChargingSession.session_id)).filter(ChargingSession.end_time.is_(None)).scalar()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        reservations_today = db.query(func.count(Reservation.reservation_id)).filter(Reservation.created_at >= today_start).scalar()

        popular_rows = (
            db.query(Station.name, Station.station_id, func.count(ChargingSession.session_id).label("session_count"))
            .join(ChargingPort, ChargingPort.station_id == Station.station_id)
            .join(Reservation, Reservation.port_id == ChargingPort.port_id)
            .join(ChargingSession, ChargingSession.reservation_id == Reservation.reservation_id)
            .group_by(Station.station_id, Station.name)
            .order_by(func.count(ChargingSession.session_id).desc())
            .limit(POPULAR_STATIONS_LIMIT)
            .all()
        )

        return {
            "total_users": total_users or 0,
            "total_companies": total_companies or 0,
            "total_stations": total_stations or 0,
            "revenue_by_day": _revenue_by_day(db),
            "system_activity_24h": system_activity_24h or 0,
            "top_actions": [{"action": row.action, "count": row.count} for row in top_actions_rows],
            "active_sessions": active_sessions or 0,
            "reservations_today": reservations_today or 0,
            "most_popular_stations": [
                {"station_id": str(row.station_id), "name": row.name, "session_count": row.session_count} for row in popular_rows
            ],
        }

    @staticmethod
    def get_operator_report(db: Session, company_id: str) -> dict:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        station_ids_subq = db.query(Station.station_id).filter(Station.company_id == company_id).scalar_subquery()
        port_ids_subq = db.query(ChargingPort.port_id).filter(ChargingPort.station_id.in_(station_ids_subq)).scalar_subquery()

        todays_reservations = (
            db.query(func.count(Reservation.reservation_id))
            .filter(Reservation.port_id.in_(port_ids_subq), Reservation.created_at >= today_start)
            .scalar()
        )

        active_sessions = (
            db.query(func.count(ChargingSession.session_id))
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .filter(Reservation.port_id.in_(port_ids_subq), ChargingSession.end_time.is_(None))
            .scalar()
        )

        revenue_since = now - timedelta(days=REVENUE_TREND_DAYS)
        revenue_total = (
            db.query(func.coalesce(func.sum(Invoice.total_amount), 0))
            .join(ChargingSession, Invoice.charging_session_id == ChargingSession.session_id)
            .join(Reservation, ChargingSession.reservation_id == Reservation.reservation_id)
            .filter(
                Reservation.port_id.in_(port_ids_subq),
                Invoice.is_paid.is_(True),
                Invoice.created_at >= revenue_since,
            )
            .scalar()
        )

        ports = db.query(ChargingPort).filter(ChargingPort.station_id.in_(station_ids_subq), ChargingPort.is_active.is_(True)).all()
        total_ports = len(ports)
        occupied_ports = sum(1 for port in ports if port.status in ("Charging", "Reserved", "Pending Waitlist"))
        utilization_pct = round((occupied_ports / total_ports) * 100, 1) if total_ports else 0.0

        maintenance_alerts = sum(
            1
            for port in ports
            if port.status in ("Maintenance", "Offline") or port.is_pending_maintenance or port.has_health_warning or port.has_blocked_warning
        )

        since = now - timedelta(days=PEAK_HOURS_WINDOW_DAYS)
        peak_hours_rows = (
            db.query(func.extract("hour", Reservation.created_at).label("hour"), func.count(Reservation.reservation_id).label("count"))
            .filter(Reservation.port_id.in_(port_ids_subq), Reservation.created_at >= since)
            .group_by("hour")
            .order_by("hour")
            .all()
        )

        queue_rows = (
            db.query(Station.name, Station.station_id, func.count(Waitlist.waitlist_id).label("count"))
            .join(Waitlist, Waitlist.station_id == Station.station_id)
            .filter(Station.station_id.in_(station_ids_subq))
            .group_by(Station.station_id, Station.name)
            .all()
        )

        return {
            "todays_reservations": todays_reservations or 0,
            "active_sessions": active_sessions or 0,
            "revenue": float(revenue_total or 0),
            "revenue_by_day": _revenue_by_day(db, port_ids=port_ids_subq),
            "charger_utilization_pct": utilization_pct,
            "maintenance_alerts": maintenance_alerts,
            "peak_hours": [{"hour": int(row.hour), "count": row.count} for row in peak_hours_rows],
            "queue_statistics": [
                {"station_id": str(row.station_id), "name": row.name, "queue_length": row.count} for row in queue_rows
            ],
        }
