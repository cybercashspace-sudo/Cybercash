from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class WithdrawalRequest:
    amount: float = 0.0
    network: str = ""
    phone: str = ""
    pin: str = ""


@dataclass
class WithdrawalResponse:
    status: str = ""
    withdrawal_id: str = ""
    reference: str = ""
    payload: dict = field(default_factory=dict)
