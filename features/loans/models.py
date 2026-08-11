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
class Loan:
    amount: float
    balance: float
    status: str
    duration: int
    created_at: str
    next_payment: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Loan":
        return cls(
            amount=float(data.get("amount") or 0.0),
            balance=float(data.get("balance") or data.get("remaining") or 0.0),
            status=str(data.get("status") or "pending"),
            duration=int(data.get("duration") or 0),
            created_at=_format_dt(data.get("created_at") or data.get("start_date")),
            next_payment=_format_dt(data.get("next_payment") or data.get("repayment_due")),
        )

