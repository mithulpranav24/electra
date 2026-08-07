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
