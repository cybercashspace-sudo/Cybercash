from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DashboardWallet:
    balance: float = 0.0
    currency: str = "GH¢"
    account_name: str = ""
    account_number: str = ""
    verified: bool = False
    payload: dict = field(default_factory=dict)


@dataclass
class DashboardTransaction:
    title: str = ""
    amount: float = 0.0
    date: str = ""
    status: str = ""
    direction: str = ""
    payload: dict = field(default_factory=dict)


@dataclass
class DashboardSnapshot:
    profile: dict = field(default_factory=dict)
    wallet: dict = field(default_factory=dict)
    transactions: list[dict] = field(default_factory=list)
    notifications: list[dict] = field(default_factory=list)
    source: str = "network"
    error_text: str = ""
