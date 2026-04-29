from datetime import datetime, timedelta
from types import SimpleNamespace

from jose import JWTError, jwt
from passlib.context import CryptContext
import logging
from backend.config import settings

# --- Monkeypatch for passlib + bcrypt 4.0+ issue ---
import bcrypt
from passlib.handlers import bcrypt as passlib_bcrypt

# This fixes the "ValueError: password cannot be longer than 72 bytes"
# which is triggered by passlib's internal check when using modern bcrypt.
# It also handles cases where passlib_bcrypt._bcrypt is None.
if not hasattr(bcrypt, "__about__"):
    bcrypt.__about__ = SimpleNamespace(__version__=getattr(bcrypt, "__version__", "unknown"))

# Force passlib to use our patched function and think it has a backend
passlib_bcrypt._bcrypt = bcrypt
if not hasattr(bcrypt, "hashpw_orig"): # avoid double patching if reloaded
    bcrypt.hashpw_orig = bcrypt.hashpw
    
    def patched_hashpw(password, salt):
        if isinstance(password, str):
            password = password.encode("utf-8")
        if len(password) > 72:
            password = password[:72]
        # Use the original function saved on the bcrypt module
        return bcrypt.hashpw_orig(password, salt)

    bcrypt.hashpw = patched_hashpw
# --------------------------------------------------

SECRET_KEY = settings.SECRET_KEY
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = 7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Password hashing
def hash_password(password: str):
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str):
    return pwd_context.verify(password, hashed)

# JWT tokens
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def create_jwt(subject, token_version: int = 0):
    return create_access_token({"sub": str(subject), "tv": int(token_version)})

def create_refresh_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
