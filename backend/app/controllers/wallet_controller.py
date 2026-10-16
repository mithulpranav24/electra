from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.wallet import PaymentMethodResponse, WalletTransactionResponse, WalletTopUpRequest
from app.services.wallet_service import WalletService
from app.models.user import User

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute)

@router.get("/balance")
def get_balance(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WalletService.get_wallet_balance(db, str(current_user.user_id))

@router.get("/payment-methods", response_model=List[PaymentMethodResponse])
def get_payment_methods(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WalletService.get_payment_methods(db, str(current_user.user_id))

@router.get("/transactions", response_model=List[WalletTransactionResponse])
def get_transactions(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WalletService.get_wallet_transactions(db, str(current_user.user_id))

@router.post("/topup", response_model=WalletTransactionResponse)
def topup_wallet(request: WalletTopUpRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return WalletService.topup_wallet(db, str(current_user.user_id), request.amount)
