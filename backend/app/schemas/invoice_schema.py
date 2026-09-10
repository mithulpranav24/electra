from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class InvoiceResponse(BaseModel):
    invoice_id: UUID
    charging_session_id: UUID
    user_id: UUID
    total_amount: Decimal
    is_paid: bool
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
