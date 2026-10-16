from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token, revoke_token, redis_client
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.services.audit_service import log_audit_event
from app.core.dependencies import get_current_user, oauth2_scheme
from app.models.user import User
import jwt
from app.core.config import settings

from app.core.response import UniformResponseRoute

router = APIRouter(route_class=UniformResponseRoute)

def _rate_limit_keys(request: Request, endpoint: str, identifier: str = None):
    client_ip = request.client.host if request.client else "unknown"
    keys = [f"rl:{endpoint}:ip:{client_ip}"]
    if identifier:
        # Normalize email identifier
        keys.append(f"rl:{endpoint}:id:{identifier.strip().lower()}")
    return keys


def check_rate_limit(request: Request, endpoint: str, identifier: str = None, count_attempt: bool = True):
    """Reject the request once either the source IP or the account is over
    its 5-per-5-minute budget.

    With count_attempt=False the caller only reads the counters; it must call
    record_failed_attempt() itself so that a *successful* request never spends
    the budget. FR-1 throttles repeated failures, not legitimate traffic.
    """
    if redis_client:
        for key in _rate_limit_keys(request, endpoint, identifier):
            attempts = redis_client.get(key)
            if attempts and int(attempts) >= 5:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
        if count_attempt:
            record_failed_attempt(request, endpoint, identifier)


def record_failed_attempt(request: Request, endpoint: str, identifier: str = None):
    if redis_client:
        for key in _rate_limit_keys(request, endpoint, identifier):
            if redis_client.incr(key) == 1:
                redis_client.expire(key, 300)


def clear_rate_limit(request: Request, endpoint: str, identifier: str = None):
    if redis_client:
        redis_client.delete(*_rate_limit_keys(request, endpoint, identifier))

@router.post("/register", response_model=UserResponse)
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    check_rate_limit(request, "register", user_in.email)
    return AuthService.register_user(db, user_in)

@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    check_rate_limit(request, "login", form_data.username, count_attempt=False)
    user = AuthService.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        record_failed_attempt(request, "login", form_data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        record_failed_attempt(request, "login", form_data.username)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")

    # A successful sign-in clears the failure budget rather than spending it.
    clear_rate_limit(request, "login", form_data.username)

    access_token = create_access_token(data={"user_id": str(user.user_id), "role": user.role})
    log_audit_event(
        db,
        user_id=user.user_id,
        action="Login",
        entity_type="USERS",
        entity_id=user.user_id,
        ip_address=request.client.host if request.client else "unknown",
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(request: Request, token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        jti = payload.get("jti")
        exp = payload.get("exp")
        user_id = payload.get("user_id")
        if jti and exp:
            revoke_token(jti, exp)
        if user_id:
            log_audit_event(
                db,
                user_id=user_id,
                action="Logout",
                entity_type="USERS",
                entity_id=user_id,
                ip_address=request.client.host if request.client else "unknown",
            )
    except jwt.InvalidTokenError:
        pass
    return {"message": "Successfully logged out"}

from app.schemas.auth import PasswordResetRequest, PasswordResetConfirm

@router.post("/forgot-password")
def forgot_password(request: Request, payload: PasswordResetRequest, db: Session = Depends(get_db)):
    check_rate_limit(request, "forgot-password", payload.email)
    AuthService.request_password_reset(db, payload.email)
    # Always return success to prevent leaking account existence
    return {"message": "If an account with that email exists, a password reset link has been generated."}

@router.post("/reset-password")
def reset_password(request: Request, payload: PasswordResetConfirm, db: Session = Depends(get_db)):
    check_rate_limit(request, "reset-password")
    success = AuthService.confirm_password_reset(db, payload.token, payload.new_password)
    if not success:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired reset token")
    return {"message": "Password has been successfully reset."}
