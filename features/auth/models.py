from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class AuthUser:
    id: int | None = None
    name: str = ""
    email: str = ""
    phone: str = ""
    token_type: str = "bearer"
    payload: dict = field(default_factory=dict)


@dataclass
class AuthSession:
    access_token: str = ""
    user: AuthUser | None = None
    status: str = ""
