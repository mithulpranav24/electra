from typing import Dict, List

from pydantic import BaseModel


class RevenueByDaySchema(BaseModel):
    date: str
    revenue: float


class TopActionSchema(BaseModel):
    action: str
    count: int


class PopularStationSchema(BaseModel):
    station_id: str
    name: str
    session_count: int


class AdminReportResponse(BaseModel):
    total_users: int
    total_companies: int
    total_stations: int
    revenue_by_day: List[RevenueByDaySchema]
    system_activity_24h: int
    top_actions: List[TopActionSchema]
    active_sessions: int
    reservations_today: int
    most_popular_stations: List[PopularStationSchema]


class PeakHourSchema(BaseModel):
    hour: int
    count: int


class QueueStatisticSchema(BaseModel):
    station_id: str
    name: str
    queue_length: int


class OperatorReportResponse(BaseModel):
    todays_reservations: int
    active_sessions: int
    revenue: float
    revenue_by_day: List[RevenueByDaySchema]
    charger_utilization_pct: float
    maintenance_alerts: int
    peak_hours: List[PeakHourSchema]
    queue_statistics: List[QueueStatisticSchema]
