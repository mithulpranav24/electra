from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
import jwt
from jwt.exceptions import InvalidTokenError
from pydantic import ValidationError

from app.core.config import settings
from app.core.database import get_db
from app.core.security import is_token_revoked
from app.models.user import User
from app.schemas.auth import TokenData

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("user_id")
        jti: str = payload.get("jti")
        if user_id is None or jti is None:
            raise credentials_exception
        token_data = TokenData(user_id=user_id, role=payload.get("role"))
    except (InvalidTokenError, ValidationError):
        raise credentials_exception
        
    if is_token_revoked(jti):
        raise HTTPException(status_code=401, detail="Token has been revoked")
        
    user = db.query(User).filter(User.user_id == token_data.user_id).first()
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    return user

def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Not enough permissions. Admin role required.")
    return current_user

def require_operator(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role not in ["Operator", "Admin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions. Operator role required.")
    return current_user

def verify_not_banned(current_user: User = Depends(get_current_user)) -> User:
    """FR-21: a 24-hour ban only prohibits making new reservations or joining
    new waitlists - it must not lock a banned user out of unrelated actions
    like stopping an in-progress session or paying an invoice. sp_CreateReservation,
    sp_JoinWaitlist, and sp_ConfirmWaitlist already re-enforce this ban at the
    database layer; this dependency exists purely so booking/waitlist endpoints
    can fail fast without a round trip."""
    if current_user.banned_until and current_user.banned_until.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
        raise HTTPException(status_code=403, detail="User is banned")
    return current_user
