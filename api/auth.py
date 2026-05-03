"""JWT authentication — simple password-based login for personal use."""

from datetime import datetime, timedelta
from jose import JWTError, jwt
from config import settings

def create_token(password: str) -> str | None:
    """Verify password and return a JWT token, or None if wrong."""
    if password != settings.JARVIS_PASSWORD:
        return None
    expire = datetime.utcnow() + timedelta(days=settings.JWT_EXPIRE_DAYS)
    return jwt.encode({"sub": "ashish", "exp": expire}, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def verify_token(token: str) -> bool:
    """Return True if the token is valid."""
    try:
        jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
        return True
    except JWTError:
        return False
