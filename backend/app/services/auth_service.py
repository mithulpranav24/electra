from sqlalchemy.orm import Session
from app.models.user import User
from app.schemas.user import UserCreate
from app.core.security import get_password_hash
from fastapi import HTTPException, status

class AuthService:
    @staticmethod
    def register_user(db: Session, user: UserCreate) -> User:
        db_user = db.query(User).filter(User.email == user.email).first()
        if db_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = get_password_hash(user.password)
        new_user = User(
            email=user.email,
            password_hash=hashed_password,
            role="Driver",
            full_name=getattr(user, "full_name", user.email.split("@")[0]),
            phone_number=getattr(user, "phone_number", None)
        )
        db.add(new_user)
        db.commit()
        db.refresh(new_user)

        # Insert a default mock payment method
        from app.models.wallet import PaymentMethod
        mock_payment = PaymentMethod(
            user_id=new_user.user_id,
            card_last4="4242",
            expiry_month=12,
            expiry_year=2030,
            is_default=True
        )
        db.add(mock_payment)
        db.commit()

        return new_user

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> User:
        from app.core.security import verify_password
        
        user = db.query(User).filter(User.email == email).first()
        if not user:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def request_password_reset(db: Session, email: str):
        from app.core.security import redis_client
        import secrets
        import hashlib
        
        user = db.query(User).filter(User.email == email).first()
        if not user or not user.is_active:
            return # Do not leak account existence
            
        token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        
        if redis_client:
            # PRD: Expire within 15 minutes (900 seconds)
            redis_client.setex(f"pw_reset:{token_hash}", 900, str(user.user_id))
            
            # In a real app we'd email the token here.
            # print(f"Reset token for {email}: {token}")

    @staticmethod
    def confirm_password_reset(db: Session, token: str, new_password: str) -> bool:
        from app.core.security import redis_client, get_password_hash
        import hashlib
        
        if not redis_client:
            return False
            
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
        user_id_bytes = redis_client.get(f"pw_reset:{token_hash}")
        
        if not user_id_bytes:
            return False
            
        user_id = user_id_bytes.decode('utf-8')
        user = db.query(User).filter(User.user_id == user_id).first()
        
        if not user or not user.is_active:
            return False
            
        user.password_hash = get_password_hash(new_password)
        db.commit()
        
        # Invalidate the token
        redis_client.delete(f"pw_reset:{token_hash}")
        
        return True
