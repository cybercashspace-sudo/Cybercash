from __future__ import annotations

from dataclasses import dataclass, field


def _clean_text(value) -> str:
    return str(value or "").strip()


def _coerce_int(value) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(value)
    except Exception:
        return None


def _coerce_bool(value, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    if text in {"true", "1", "yes", "y", "on"}:
        return True
    if text in {"false", "0", "no", "n", "off"}:
        return False
    return default


@dataclass
class User:
    id: int | None = None
    momo_number: str = ""
    email: str = ""
    phone_number: str = ""
    full_name: str = ""
    first_name: str = ""
    is_active: bool = True
    is_admin: bool = False
    is_verified: bool = False
    is_agent: bool = False
    role: str = "user"
    status: str = "active"
    payload: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.full_name or self.first_name or ""

    @classmethod
    def from_payload(cls, payload: dict | None) -> "User":
        data = dict(payload or {})
        full_name = _clean_text(data.get("full_name") or data.get("name"))
        first_name = _clean_text(data.get("first_name"))
        if not first_name and full_name:
            first_name = full_name.split()[0]

        return cls(
            id=_coerce_int(data.get("id")),
            momo_number=_clean_text(data.get("momo_number") or data.get("phone_number")),
            email=_clean_text(data.get("email")),
            phone_number=_clean_text(data.get("phone_number") or data.get("phone")),
            full_name=full_name,
            first_name=first_name,
            is_active=_coerce_bool(data.get("is_active"), default=True),
            is_admin=_coerce_bool(data.get("is_admin")),
            is_verified=_coerce_bool(data.get("is_verified")),
            is_agent=_coerce_bool(data.get("is_agent")),
            role=_clean_text(data.get("role")) or "user",
            status=_clean_text(data.get("status")) or "active",
            payload=data,
        )

    def to_dict(self) -> dict:
        data = dict(self.payload)
        data.update(
            {
                "id": self.id,
                "momo_number": self.momo_number,
                "email": self.email,
                "phone_number": self.phone_number,
                "full_name": self.full_name,
                "first_name": self.first_name,
                "is_active": self.is_active,
                "is_admin": self.is_admin,
                "is_verified": self.is_verified,
                "is_agent": self.is_agent,
                "role": self.role,
                "status": self.status,
            }
        )
        return data
