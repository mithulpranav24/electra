from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.audit import AuditLog


def log_audit_event(
    db: Session,
    user_id: Optional[UUID],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[UUID] = None,
    details: Optional[dict] = None,
    ip_address: str = "unknown",
    commit: bool = True,
) -> AuditLog:
    """FR-26 audit interceptor: the single place every controller/service/worker
    routes an audit entry through, instead of each call site constructing and
    committing its own AuditLog row.

    AUDIT_LOGS is immutable (trg_enforce_immutability) and Postgres has no
    autonomous transactions, so a stored-procedure-driven flow can't write its
    own audit row mid-procedure - the SP's CALL is committed first (via the
    caller's own db.commit()), and this function's default commit=True then
    adds and immediately commits the audit row as its own follow-up
    transaction, guaranteeing it's durable before the HTTP response returns.

    Pass commit=False when the audit row should instead be folded into a
    still-open transaction the caller is about to commit alongside other
    plain ORM changes (e.g. a session settlement's invoice + wallet ledger +
    reservation status change) - that makes the audit entry atomic with the
    state it describes, which is a strictly stronger guarantee than a
    separate transaction for those non-SP flows.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        ip_address=str(ip_address) if ip_address is not None else "unknown",
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry
