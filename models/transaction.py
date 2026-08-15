from __future__ import annotations

from dataclasses import dataclass, field


def _clean_text(value) -> str:
    return str(value or "").strip()


def _coerce_float(value, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return float(default)
        return float(value)
    except Exception:
        return float(default)


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
class Transaction:
    id: str = ""
    type: str = ""
    amount: float = 0.0
    status: str = ""
    created_at: str = ""
    description: str = ""
    reference: str = ""
    direction: str = ""
    is_read: bool = True
    payload: dict = field(default_factory=dict)

    @property
    def title(self) -> str:
        return self.description or self.type or "Transaction"

    @classmethod
    def from_payload(cls, payload: dict | None) -> "Transaction":
        data = dict(payload or {})
        return cls(
            id=_clean_text(data.get("id") or data.get("transaction_id")),
            type=_clean_text(data.get("type") or data.get("transaction_type") or "Transaction"),
            amount=_coerce_float(data.get("amount")),
            status=_clean_text(data.get("status") or data.get("state")),
            created_at=_clean_text(data.get("created_at") or data.get("date") or data.get("timestamp")),
            description=_clean_text(data.get("description")),
            reference=_clean_text(data.get("reference")),
            direction=_clean_text(data.get("direction") or data.get("flow")),
            is_read=_coerce_bool(data.get("is_read"), default=True),
            payload=data,
        )

    def to_dict(self) -> dict:
        data = dict(self.payload)
        data.update(
            {
                "id": self.id,
                "transaction_id": self.id,
                "type": self.type,
                "amount": self.amount,
                "status": self.status,
                "created_at": self.created_at,
                "description": self.description,
                "reference": self.reference,
                "direction": self.direction,
                "is_read": self.is_read,
            }
        )
        return data
