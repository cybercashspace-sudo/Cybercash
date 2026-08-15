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


def _coerce_int(value, default: int = 1) -> int:
    try:
        if value is None or value == "":
            return int(default)
        return int(value)
    except Exception:
        return int(default)


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
class Wallet:
    balance: float = 0.0
    escrow_balance: float = 0.0
    loan_balance: float = 0.0
    investment_balance: float = 0.0
    currency: str = "GH¢"
    account_name: str = ""
    account_number: str = ""
    verified: bool = False
    version: int = 1
    payload: dict = field(default_factory=dict)

    @classmethod
    def from_payload(cls, payload: dict | None) -> "Wallet":
        data = dict(payload or {})
        return cls(
            balance=_coerce_float(data.get("balance")),
            escrow_balance=_coerce_float(data.get("escrow_balance")),
            loan_balance=_coerce_float(data.get("loan_balance")),
            investment_balance=_coerce_float(data.get("investment_balance")),
            currency=_clean_text(data.get("currency")) or "GH¢",
            account_name=_clean_text(data.get("account_name") or data.get("name")),
            account_number=_clean_text(data.get("account_number") or data.get("wallet_number")),
            verified=_coerce_bool(data.get("verified") or data.get("is_verified") or data.get("status") == "verified"),
            version=_coerce_int(data.get("version"), default=1),
            payload=data,
        )

    def to_dict(self) -> dict:
        data = dict(self.payload)
        data.update(
            {
                "balance": self.balance,
                "escrow_balance": self.escrow_balance,
                "loan_balance": self.loan_balance,
                "investment_balance": self.investment_balance,
                "currency": self.currency,
                "account_name": self.account_name,
                "account_number": self.account_number,
                "verified": self.verified,
                "version": self.version,
            }
        )
        return data
