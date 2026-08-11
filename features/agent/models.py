from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


def _format_dt(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y %I:%M %p")
    except ValueError:
        return text


@dataclass
class Agent:
    id: str
    name: str
    status: str
    commission: float
    verified: bool
    today_sales: float = 0.0
    customers_served: int = 0
    wallet_balance: float = 0.0

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Agent":
        return cls(
            id=str(data.get("id") or data.get("agent_id") or ""),
            name=str(data.get("name") or data.get("full_name") or "Agent"),
            status=str(data.get("status") or "pending"),
            commission=float(data.get("commission") or data.get("commission_balance") or 0.0),
            verified=bool(data.get("verified") or data.get("is_verified") or False),
            today_sales=float(data.get("today_sales") or 0.0),
            customers_served=int(data.get("customers_served") or 0),
            wallet_balance=float(data.get("wallet_balance") or 0.0),
        )


@dataclass
class AgentTransaction:
    transaction_id: str
    title: str
    amount_text: str
    status_text: str
    date_text: str
    description: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentTransaction":
        amount = float(data.get("amount") or 0.0)
        tx_type = str(data.get("type") or data.get("title") or "agent").replace("_", " ").title()
        return cls(
            transaction_id=str(data.get("id") or data.get("transaction_id") or data.get("reference") or ""),
            title=tx_type,
            amount_text=f"{'+' if amount >= 0 else '-'} GH₵ {abs(amount):,.2f}",
            status_text=str(data.get("status") or "Completed").replace("_", " ").title(),
            date_text=_format_dt(data.get("created_at") or data.get("date")),
            description=str(data.get("description") or ""),
        )

