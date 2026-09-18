from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID


class MaintenanceScheduleCreate(BaseModel):
    port_id: UUID
    start_time: datetime
    end_time: datetime


class MaintenanceScheduleResponse(BaseModel):
    maintenance_id: UUID
    port_id: UUID
    start_time: datetime
    end_time: datetime
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
