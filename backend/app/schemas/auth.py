from pydantic import BaseModel, field_validator

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    user_id: str | None = None
    role: str | None = None

class PasswordResetRequest(BaseModel):
    email: str

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str

    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v: str) -> str:
        common_passwords = {'password', '12345678', 'password123', 'admin123', 'qwertyuiop', '11111111'}
        if v.lower() in common_passwords:
            raise ValueError("Password is too common or breached")
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v
