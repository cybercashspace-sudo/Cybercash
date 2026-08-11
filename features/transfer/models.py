from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TransferRecipient:
    identifier: str = ""
    name: str = ""
    wallet_id: str = ""
    payload: dict = field(default_factory=dict)


@dataclass
class TransferRequest:
    recipient: str = ""
    amount: float = 0.0
    pin: str = ""
    description: str = ""


@dataclass
class TransferResponse:
    status: str = ""
    reference: str = ""
    payload: dict = field(default_factory=dict)
