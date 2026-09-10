from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.invoice import Invoice
from app.models.user import User
from app.schemas.invoice_schema import InvoiceResponse

router = APIRouter(prefix="/invoices", tags=["Invoices"])


@router.get("", response_model=List[InvoiceResponse])
def list_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Invoice)
        .filter(Invoice.user_id == current_user.user_id)
        .order_by(Invoice.created_at.desc())
        .all()
    )


@router.post("/pay")
def pay_outstanding_invoices(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """FR-16 mock payment endpoint: the wallet is a single pooled balance, not
    earmarked per invoice, so an unpaid invoice means the settlement at session
    end left wallet_balance negative. Once the user tops up enough to clear
    that debt, every outstanding invoice is marked paid and the account
    unsuspends - there's no separate per-invoice amount to reconcile."""
    user = db.query(User).with_for_update().filter(User.user_id == current_user.user_id).first()
    if user.wallet_balance < 0:
        raise HTTPException(
            status_code=400,
            detail=f"Wallet balance is still negative (₹{user.wallet_balance}). Top up at least ₹{-user.wallet_balance} before paying.",
        )

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    unpaid = db.query(Invoice).filter(Invoice.user_id == current_user.user_id, Invoice.is_paid.is_(False)).with_for_update().all()
    for invoice in unpaid:
        invoice.is_paid = True
        invoice.paid_at = now

    user.is_suspended = False
    db.commit()
    return {"success": True, "message": f"Settled {len(unpaid)} outstanding invoice(s)."}
