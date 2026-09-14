from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID

class StationSearchRequest(BaseModel):
    lat: float = Field(..., description="Latitude of the center point")
    lng: float = Field(..., description="Longitude of the center point")
    radius_km: float = Field(10.0, description="Search radius in kilometers", ge=0.1, le=500.0)
    connector_type: Optional[str] = Field(None, description="Filter by specific connector type")
    min_power_kw: Optional[float] = Field(None, description="Minimum charging power in kW")


class SearchHistoryEntry(BaseModel):
    search_id: UUID
    lat: float
    lng: float
    radius_km: float
    connector_type: Optional[str] = None
    min_power_kw: Optional[float] = None
    created_at: datetime
