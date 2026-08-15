from __future__ import annotations

from core.auth import AuthService as _CoreAuthService
from models.user import User


class AuthService(_CoreAuthService):
    """App-facing auth facade that reuses the existing core auth service."""

    @staticmethod
    def to_user_model(payload: dict | None) -> User:
        return User.from_payload(payload)


__all__ = ["AuthService"]
