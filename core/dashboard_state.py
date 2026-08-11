from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DashboardState:
    """Lightweight in-memory dashboard snapshot."""

    user: dict | None = None
    wallet: dict | None = None
    transactions: list[dict] = field(default_factory=list)
    notifications: list[dict] = field(default_factory=list)
    online: bool = True
    loading: bool = False
    source: str = "live"

    def reset(self) -> None:
        self.user = None
        self.wallet = None
        self.transactions = []
        self.notifications = []
        self.online = True
        self.loading = False
        self.source = "live"

