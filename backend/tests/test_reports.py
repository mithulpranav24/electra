from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


class _Query:
    """A single db.query(...) call's chain. Any attribute access other than
    the configured terminal (e.g. .filter()/.join()/.group_by()/.order_by()/
    .limit()/.scalar_subquery()) returns self so the chain keeps flowing;
    the terminal call returns the configured value. Every chained call is
    recorded so tests can assert on the actual filter/join arguments passed,
    which is what lets these mock-only tests catch a missing WHERE clause
    (e.g. a revenue query that forgot to scope by date)."""

    def __init__(self, terminal, value):
        self._terminal = terminal
        self._value = value
        self.calls = {}

    def __getattr__(self, name):
        if name == self._terminal:
            return lambda *a, **k: self._value

        def _chain(*a, **k):
            self.calls.setdefault(name, []).append((a, k))
            return self

        return _chain


def _mock_db(queries):
    db = MagicMock()
    db.query.side_effect = queries
    return db


def _filter_args_text(query: _Query) -> str:
    """Flattens every positional arg across every .filter() call on this
    query into one string, for substring assertions against the compiled
    SQLAlchemy expression (e.g. 'invoices.created_at >=')."""
    parts = []
    for args, _ in query.calls.get("filter", []):
        parts.extend(str(a) for a in args)
    return " ".join(parts)


class TestAdminReport:
    def test_get_admin_report_shape_and_values(self):
        from app.services.report_service import ReportService

        top_action_rows = [SimpleNamespace(action="Waitlist Joined", count=3)]
        popular_rows = [SimpleNamespace(station_id="11111111-1111-1111-1111-111111111111", name="Koramangala", session_count=9)]
        revenue_rows = [SimpleNamespace(day=date(2026, 9, 1), revenue=1500.0)]

        db = _mock_db(
            [
                _Query("scalar", 42),  # total_users
                _Query("scalar", 5),  # total_companies
                _Query("scalar", 10),  # total_stations
                _Query("scalar", 100),  # system_activity_24h
                _Query("all", top_action_rows),  # top_actions_rows
                _Query("scalar", 3),  # active_sessions
                _Query("scalar", 7),  # reservations_today
                _Query("all", popular_rows),  # popular_rows
                _Query("all", revenue_rows),  # _revenue_by_day
            ]
        )

        result = ReportService.get_admin_report(db)

        assert result["total_users"] == 42
        assert result["total_companies"] == 5
        assert result["total_stations"] == 10
        assert result["system_activity_24h"] == 100
        assert result["active_sessions"] == 3
        assert result["reservations_today"] == 7
        assert result["top_actions"] == [{"action": "Waitlist Joined", "count": 3}]
        assert result["most_popular_stations"] == [
            {"station_id": "11111111-1111-1111-1111-111111111111", "name": "Koramangala", "session_count": 9}
        ]
        assert result["revenue_by_day"] == [{"date": "2026-09-01", "revenue": 1500.0}]

    def test_get_admin_report_treats_none_scalars_as_zero(self):
        from app.services.report_service import ReportService

        db = _mock_db(
            [
                _Query("scalar", None),
                _Query("scalar", None),
                _Query("scalar", None),
                _Query("scalar", None),
                _Query("all", []),
                _Query("scalar", None),
                _Query("scalar", None),
                _Query("all", []),
                _Query("all", []),
            ]
        )

        result = ReportService.get_admin_report(db)

        assert result["total_users"] == 0
        assert result["active_sessions"] == 0
        assert result["reservations_today"] == 0
        assert result["revenue_by_day"] == []


class TestOperatorReport:
    def _ports(self):
        return [
            SimpleNamespace(status="Charging", is_pending_maintenance=False, has_health_warning=False, has_blocked_warning=False),
            SimpleNamespace(status="Available", is_pending_maintenance=False, has_health_warning=False, has_blocked_warning=False),
            SimpleNamespace(status="Maintenance", is_pending_maintenance=False, has_health_warning=False, has_blocked_warning=False),
            SimpleNamespace(status="Reserved", is_pending_maintenance=True, has_health_warning=False, has_blocked_warning=False),
        ]

    def _queries(self, revenue_value=2500.0, ports=None, revenue_rows=None):
        return [
            _Query("scalar_subquery", MagicMock(name="station_ids_subq")),  # station_ids_subq
            _Query("scalar_subquery", MagicMock(name="port_ids_subq")),  # port_ids_subq
            _Query("scalar", 4),  # todays_reservations
            _Query("scalar", 2),  # active_sessions
            revenue_query := _Query("scalar", revenue_value),  # revenue_total
            _Query("all", ports if ports is not None else self._ports()),  # ports
            _Query("all", [SimpleNamespace(hour=14, count=6)]),  # peak_hours_rows
            _Query("all", [SimpleNamespace(name="MG Road", station_id="22222222-2222-2222-2222-222222222222", count=2)]),  # queue_rows
            _Query("all", revenue_rows if revenue_rows is not None else []),  # _revenue_by_day
        ], revenue_query

    def test_get_operator_report_shape_and_values(self):
        from app.services.report_service import ReportService

        queries, _ = self._queries()
        db = _mock_db(queries)

        result = ReportService.get_operator_report(db, "33333333-3333-3333-3333-333333333333")

        assert result["todays_reservations"] == 4
        assert result["active_sessions"] == 2
        assert result["revenue"] == 2500.0
        # 2 of 4 ports occupied (Charging, Reserved) -> 50.0%
        assert result["charger_utilization_pct"] == 50.0
        # Maintenance status + is_pending_maintenance flag -> 2 alerts
        assert result["maintenance_alerts"] == 2
        assert result["peak_hours"] == [{"hour": 14, "count": 6}]
        assert result["queue_statistics"] == [
            {"station_id": "22222222-2222-2222-2222-222222222222", "name": "MG Road", "queue_length": 2}
        ]

    def test_get_operator_report_zero_ports_has_zero_utilization(self):
        from app.services.report_service import ReportService

        queries, _ = self._queries(ports=[])
        db = _mock_db(queries)

        result = ReportService.get_operator_report(db, "33333333-3333-3333-3333-333333333333")

        assert result["charger_utilization_pct"] == 0.0
        assert result["maintenance_alerts"] == 0

    def test_get_operator_report_revenue_is_scoped_to_a_date_window(self):
        """Regression test: the operator revenue stat card is documented and
        labeled (frontend Reports.tsx) as a 30-day figure, matching the 30-day
        revenue trend chart on the same page. If this query drops its
        Invoice.created_at lower bound, it silently reverts to all-time
        revenue and the two numbers on the page stop agreeing."""
        from app.services.report_service import ReportService

        queries, revenue_query = self._queries()
        db = _mock_db(queries)

        ReportService.get_operator_report(db, "33333333-3333-3333-3333-333333333333")

        assert "created_at >=" in _filter_args_text(revenue_query)
        assert "is_paid" in _filter_args_text(revenue_query)
