from __future__ import annotations

from dataclasses import dataclass, field


def _as_dict(value) -> dict:
    return dict(value or {}) if isinstance(value, dict) else {}


def _as_list(value) -> list[dict]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


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

    def apply(
        self,
        payload: dict | None = None,
        *,
        source: str | None = None,
        online: bool | None = None,
        loading: bool | None = None,
    ) -> "DashboardState":
        data = dict(payload or {})
        profile = _as_dict(data.get("profile") or data.get("user"))
        wallet = _as_dict(data.get("wallet"))
        transactions = _as_list(data.get("transactions"))
        notifications = _as_list(data.get("notifications"))

        self.user = profile
        self.wallet = wallet
        self.transactions = transactions
        self.notifications = notifications

        if source is not None:
            self.source = str(source or "live")
        if online is not None:
            self.online = bool(online)
        if loading is not None:
            self.loading = bool(loading)
        return self

    def snapshot(self) -> dict[str, object]:
        profile = _as_dict(self.user)
        wallet = _as_dict(self.wallet)
        transactions = _as_list(self.transactions)
        notifications = _as_list(self.notifications)
        return {
            "profile": profile,
            "user": dict(profile),
            "wallet": wallet,
            "transactions": transactions,
            "notifications": notifications,
            "online": bool(self.online),
            "loading": bool(self.loading),
            "source": str(self.source or "live"),
        }

    def reset(self) -> None:
        self.user = None
        self.wallet = None
        self.transactions = []
        self.notifications = []
        self.online = True
        self.loading = False
        self.source = "live"
