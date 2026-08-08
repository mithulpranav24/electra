from sqlalchemy.orm import Session
from app.models.wallet import PaymentMethod, WalletTransaction
from app.models.user import User
from fastapi import HTTPException
from decimal import Decimal

class WalletService:
    @staticmethod
    def get_payment_methods(db: Session, user_id: str):
        return db.query(PaymentMethod).filter(PaymentMethod.user_id == user_id).all()

    @staticmethod
    def get_wallet_transactions(db: Session, user_id: str):
        return db.query(WalletTransaction).filter(WalletTransaction.user_id == user_id).order_by(WalletTransaction.created_at.desc()).all()

    @staticmethod
    def get_wallet_balance(db: Session, user_id: str):
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return {"balance": user.wallet_balance}

    @staticmethod
    def topup_wallet(db: Session, user_id: str, amount: Decimal):
        if amount <= 0:
            raise HTTPException(status_code=400, detail="Amount must be positive")
        
        # Verify user has a payment method
        has_method = db.query(PaymentMethod).filter(PaymentMethod.user_id == user_id).first()
        if not has_method:
            raise HTTPException(status_code=400, detail="No payment method linked to account")
            
        transaction = WalletTransaction(
            user_id=user_id,
            amount=amount,
            transaction_type="Top-Up"
        )
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        # Balance is automatically updated by the database trigger
        return transaction
