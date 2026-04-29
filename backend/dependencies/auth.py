from datetime import datetime, timezone
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import or_, select

from backend.database import async_session
from backend.models import User
from backend.config import settings  # Make sure you have SECRET_KEY here


# ==========================================
# OAUTH2 SCHEME
# ==========================================

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ==========================================
# VERIFY TOKEN + GET CURRENT USER
# ==========================================

async def get_current_user(token: str = Depends(oauth2_scheme)) -> User:
    """
    Decodes JWT token and returns authenticated user.
    """

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=["HS256"],
        )
        subject = payload.get("sub")
        if subject is None:
            raise credentials_exception
        token_version_claim = payload.get("tv")

    except JWTError:
        raise credentials_exception

    async with async_session() as session:
        # Backward compatible subject lookup:
        # modern tokens use numeric user id in "sub"; legacy tests/tokens may use email.
        user_id: int | None = None
        try:
            user_id = int(str(subject))
        except (TypeError, ValueError):
            user_id = None

        if user_id is not None:
            result = await session.execute(select(User).where(User.id == user_id))
        else:
            subject_str = str(subject or "").strip()
            if not subject_str:
                raise credentials_exception
            result = await session.execute(
                select(User).where(
                    or_(
                        User.email == subject_str,
                        User.phone_number == subject_str,
                        User.momo_number == subject_str,
                    )
                )
            )
        user = result.scalar_one_or_none()

        if user is None:
            raise credentials_exception

        # Token revocation check via token_version.
        # - New app tokens carry "tv" and must match exactly.
        # - Legacy tokens without "tv" are accepted only while token_version == 0.
        current_tv = int(getattr(user, "token_version", 0) or 0)
        if token_version_claim is None:
            if current_tv > 0:
                raise credentials_exception
        else:
            try:
                token_tv = int(token_version_claim)
            except (TypeError, ValueError):
                raise credentials_exception
            if token_tv != current_tv:
                raise credentials_exception

        # Optional: block inactive users, but keep admin/super_admin accounts usable.
        role = str(getattr(user, "role", "") or "").strip().lower()
        is_privileged_admin = bool(getattr(user, "is_admin", False)) or role in {"admin", "super_admin"}
        if hasattr(user, "status") and user.status != "active" and not is_privileged_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account inactive",
            )

        return user


# ==========================================
# ROLE CHECK (SUPER ADMIN)
# ==========================================

async def require_super_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensures the user is a super admin.
    """

    if getattr(current_user, "role", "user") != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )

    return current_user


async def require_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Ensures the user is an administrator (admin or super_admin).
    """
    role = str(getattr(current_user, "role", "") or "").strip().lower()
    if not bool(getattr(current_user, "is_admin", False)) and role not in {"admin", "super_admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return current_user
