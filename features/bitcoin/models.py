from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_dt(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d %b %Y %I:%M %p")
    text = str(value)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y %I:%M %p")
    except ValueError:
        return text


@dataclass
class BitcoinWallet:
    balance: float = 0.0
    usd_value: float = 0.0
    address: str = ""
    status: str = "active"

    @classmethod
    def from_dict(cls, data: Dict[str, Any] | None) -> "BitcoinWallet":
        payload = data or {}
        return cls(
            balance=_to_float(payload.get("balance")),
            usd_value=_to_float(payload.get("usd_value") or payload.get("value_usd")),
            address=str(payload.get("address") or payload.get("wallet_address") or ""),
            status=str(payload.get("status") or "active"),
        )


@dataclass
class BitcoinTransaction:
    transaction_id: str
    title: str
    amount_text: str
    status: str
    status_text: str
    created_at: str
    date_text: str
    description: str = ""
    reference: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BitcoinTransaction":
        tx_type = str(data.get("type") or data.get("title") or "bitcoin").replace("_", " ").title()
        amount = data.get("amount")
        amount_value = _to_float(amount)
        is_credit = amount_value >= 0
        symbol = "₿"
        amount_text = data.get("amount_text") or f"{'+' if is_credit else '-'} {symbol} {abs(amount_value):,.6f}"
        created_at = str(data.get("created_at") or data.get("date") or "")
        return cls(
            transaction_id=str(data.get("id") or data.get("transaction_id") or data.get("reference") or ""),
            title=tx_type,
            amount_text=amount_text,
            status=str(data.get("status") or "completed"),
            status_text=str(data.get("status_text") or str(data.get("status") or "completed").replace("_", " ").title()),
            created_at=created_at,
            date_text=data.get("date_text") or _format_dt(created_at),
            description=str(data.get("description") or ""),
            reference=str(data.get("reference") or data.get("transaction_id") or ""),
        )

