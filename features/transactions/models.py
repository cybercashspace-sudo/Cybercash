from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Transaction:
    id: str = ""
    type: str = ""
    amount: float = 0.0
    status: str = ""
    created_at: str = ""
    description: str = ""
    reference: str = ""
    payload: dict = field(default_factory=dict)
