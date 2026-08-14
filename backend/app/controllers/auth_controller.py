from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import create_access_token, revoke_token, redis_client
from app.schemas.auth import Token
from app.schemas.user import UserCreate, UserResponse
from app.services.auth_service import AuthService
from app.core.dependencies import get_current_user, oauth2_scheme
from app.models.user import User
import jwt
from app.core.config import settings

router = APIRouter()

def check_rate_limit(request: Request, endpoint: str, identifier: str = None):
    if redis_client:
        client_ip = request.client.host if request.client else "unknown"
        
        # Check IP
        ip_key = f"rl:{endpoint}:ip:{client_ip}"
        ip_attempts = redis_client.get(ip_key)
        if ip_attempts and int(ip_attempts) >= 5:
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
        
        # Check Identifier
        if identifier:
            # Normalize email identifier
            norm_identifier = identifier.strip().lower()
            id_key = f"rl:{endpoint}:id:{norm_identifier}"
            id_attempts = redis_client.get(id_key)
            if id_attempts and int(id_attempts) >= 5:
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
            
            redis_client.incr(id_key)
            if not id_attempts:
                redis_client.expire(id_key, 300)

        redis_client.incr(ip_key)
        if not ip_attempts:
            redis_client.expire(ip_key, 300)

@router.post("/register", response_model=UserResponse)
def register(request: Request, user_in: UserCreate, db: Session = Depends(get_db)):
    check_rate_limit(request, "register", user_in.email)
    return AuthService.register_user(db, user_in)

@router.post("/login", response_model=Token)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    check_rate_limit(request, "login", form_data.username)
    user = AuthService.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user")
    
    access_token = create_access_token(data={"user_id": str(user.user_id), "role": user.role})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/logout")
def logout(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            revoke_token(jti, exp)
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
