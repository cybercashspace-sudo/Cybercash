from __future__ import annotations

from kivy.event import EventDispatcher
from kivy.properties import BooleanProperty, DictProperty, ListProperty, NumericProperty, StringProperty


class AppState(EventDispatcher):
    """Shared application state used by screens and services."""

    user = DictProperty({})
    wallet = DictProperty({})
    transactions = ListProperty([])
    dashboard = DictProperty({})
    theme = StringProperty("dark")
    notifications = ListProperty([])
    unread_notifications = NumericProperty(0)
    is_online = BooleanProperty(True)
    current_screen = StringProperty("")
    previous_screen = StringProperty("")

    def _sync_dashboard(self) -> None:
        dashboard = dict(self.dashboard or {})
        dashboard.update(
            {
                "user": dict(self.user or {}),
                "wallet": dict(self.wallet or {}),
                "transactions": list(self.transactions or []),
                "notifications": list(self.notifications or []),
                "unread_notifications": int(self.unread_notifications or 0),
                "online": bool(self.is_online),
                "current_screen": str(self.current_screen or ""),
                "previous_screen": str(self.previous_screen or ""),
                "theme": str(self.theme or "dark"),
            }
        )
        self.dashboard = dashboard

    def set_user(self, payload: dict | None) -> None:
        self.user = dict(payload or {})
        self._sync_dashboard()

    def set_wallet(self, payload: dict | None) -> None:
        self.wallet = dict(payload or {})
        self._sync_dashboard()

    def set_transactions(self, items: list | None) -> None:
        self.transactions = list(items or [])
        self._sync_dashboard()

    def set_notifications(self, items: list | None) -> None:
        notifications = list(items or [])
        self.notifications = notifications
        self.unread_notifications = sum(1 for item in notifications if not bool((item or {}).get("read", False)))
        self._sync_dashboard()

    def set_online(self, value: bool) -> None:
        self.is_online = bool(value)
        self._sync_dashboard()

    def set_screen(self, current: str, previous: str = "") -> None:
        self.current_screen = str(current or "").strip()
        self.previous_screen = str(previous or "").strip()
        self._sync_dashboard()

    def set_dashboard(
        self,
        payload: dict | None = None,
        *,
        user: dict | None = None,
        wallet: dict | None = None,
        transactions: list | None = None,
        notifications: list | None = None,
        online: bool | None = None,
        loading: bool | None = None,
        source: str | None = None,
        current_screen: str | None = None,
        previous_screen: str | None = None,
    ) -> None:
        data = dict(payload or {})
        if user is None:
            user = data.get("user") or data.get("profile")
        if wallet is None:
            wallet = data.get("wallet")
        if transactions is None:
            transactions = data.get("transactions")
        if notifications is None:
            notifications = data.get("notifications")
        if online is None and "online" in data:
            online = bool(data.get("online"))
        if loading is None and "loading" in data:
            loading = bool(data.get("loading"))
        if source is None and "source" in data:
            source = str(data.get("source") or "")
        if current_screen is None and "current_screen" in data:
            current_screen = str(data.get("current_screen") or "")
        if previous_screen is None and "previous_screen" in data:
            previous_screen = str(data.get("previous_screen") or "")

        self.user = dict(user or {})
        self.wallet = dict(wallet or {})
        self.transactions = list(transactions or [])
        self.notifications = list(notifications or [])
        self.unread_notifications = sum(1 for item in self.notifications if not bool((item or {}).get("read", False)))
        if online is not None:
            self.is_online = bool(online)
        if current_screen is not None:
            self.current_screen = str(current_screen or "").strip()
        if previous_screen is not None:
            self.previous_screen = str(previous_screen or "").strip()

        dashboard = dict(data)
        dashboard.update(
            {
                "user": dict(self.user or {}),
                "wallet": dict(self.wallet or {}),
                "transactions": list(self.transactions or []),
                "notifications": list(self.notifications or []),
                "online": bool(self.is_online),
                "loading": bool(loading) if loading is not None else bool(data.get("loading", False)),
                "source": str(source or data.get("source") or "live"),
                "current_screen": str(self.current_screen or ""),
                "previous_screen": str(self.previous_screen or ""),
                "unread_notifications": int(self.unread_notifications or 0),
            }
        )
        self.dashboard = dashboard

    def reset(self) -> None:
        self.user = {}
        self.wallet = {}
        self.transactions = []
        self.dashboard = {}
        self.notifications = []
        self.unread_notifications = 0
        self.is_online = True
        self.current_screen = ""
        self.previous_screen = ""
        self._sync_dashboard()
