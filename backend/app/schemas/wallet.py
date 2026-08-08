from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from uuid import UUID
from decimal import Decimal

class PaymentMethodResponse(BaseModel):
    payment_method_id: UUID
    card_last4: str
    expiry_month: int
    expiry_year: int
    is_default: bool
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class WalletTransactionResponse(BaseModel):
    transaction_id: UUID
    amount: Decimal
    transaction_type: str
    reference_id: Optional[UUID]
    created_at: datetime

    class Config:
        orm_mode = True
        from_attributes = True

class WalletTopUpRequest(BaseModel):
    amount: Decimal
