from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


def _format_dt(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y")
    except ValueError:
        return text


@dataclass
class Investment:
    amount: float
    duration: int
    earned: float
    status: str
    start_date: str
    end_date: str
    balance: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Investment":
        return cls(
            amount=float(data.get("amount") or 0.0),
            duration=int(data.get("duration") or data.get("days") or 0),
            earned=float(data.get("earned") or data.get("returns") or 0.0),
            status=str(data.get("status") or "pending"),
            start_date=_format_dt(data.get("start_date") or data.get("created_at")),
            end_date=_format_dt(data.get("end_date") or data.get("maturity_date")),
            balance=float(data.get("balance") or 0.0),
        )

