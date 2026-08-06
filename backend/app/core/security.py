import jwt
from datetime import datetime, timedelta, timezone
import bcrypt
import uuid
import redis
from app.core.config import settings

redis_client = None
if settings.redis_url:
    redis_client = redis.from_url(settings.redis_url)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))

def get_password_hash(password: str) -> str:
    # Ensure password is at most 72 bytes
    pwd_bytes = password.encode('utf-8')[:72]
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode('utf-8')

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    jti = str(uuid.uuid4())
    to_encode.update({"exp": expire, "jti": jti})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt

def is_token_revoked(jti: str) -> bool:
    if redis_client is None:
        return False
    try:
        return redis_client.exists(f"revoked_tokens:{jti}") > 0
    except Exception:
        # fail open if redis is down
        return False

def revoke_token(jti: str, exp_timestamp: int):
    if redis_client:
        try:
            current_time = int(datetime.now(timezone.utc).timestamp())
            ttl = exp_timestamp - current_time
            if ttl > 0:
                redis_client.setex(f"revoked_tokens:{jti}", ttl, "true")
        except Exception:
            pass
