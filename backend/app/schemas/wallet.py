from pydantic import BaseModel, ConfigDict
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

    model_config = ConfigDict(from_attributes=True)

class WalletTransactionResponse(BaseModel):
    transaction_id: UUID
    amount: Decimal
    transaction_type: str
    reference_id: Optional[UUID]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class WalletTopUpRequest(BaseModel):
    amount: Decimal
