from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DepositRequest:
    amount: float = 0.0
    method: str = "paystack"


@dataclass
class DepositResponse:
    status: str = ""
    reference: str = ""
    authorization_url: str = ""
    payload: dict = field(default_factory=dict)
