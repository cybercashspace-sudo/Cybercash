from __future__ import annotations

from kivy.event import EventDispatcher
from kivy.properties import BooleanProperty, DictProperty, ListProperty, NumericProperty, StringProperty


class AppState(EventDispatcher):
    """Shared application state used by screens and services."""

    user = DictProperty({})
    wallet = DictProperty({})
    theme = StringProperty("dark")
    notifications = ListProperty([])
    unread_notifications = NumericProperty(0)
    is_online = BooleanProperty(True)

    def set_user(self, payload: dict | None) -> None:
        self.user = dict(payload or {})

    def set_wallet(self, payload: dict | None) -> None:
        self.wallet = dict(payload or {})

    def set_notifications(self, items: list | None) -> None:
        notifications = list(items or [])
        self.notifications = notifications
        self.unread_notifications = sum(1 for item in notifications if not bool((item or {}).get("read", False)))

    def set_online(self, value: bool) -> None:
        self.is_online = bool(value)

    def reset(self) -> None:
        self.user = {}
        self.wallet = {}
        self.notifications = []
        self.unread_notifications = 0
        self.is_online = True

