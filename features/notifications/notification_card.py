from __future__ import annotations

from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from widgets import GlassCard


def _style_for_type(notification_type: str):
    kind = str(notification_type or "").strip().lower()
    if "withdraw" in kind:
        return "bank-transfer", [0.95, 0.67, 0.18, 1]
    if "transfer" in kind:
        return "swap-horizontal", [0.60, 0.78, 1.00, 1]
    if "deposit" in kind:
        return "cash-plus", [0.50, 0.88, 0.60, 1]
    if "security" in kind or "login" in kind:
        return "shield-lock", [0.96, 0.76, 0.12, 1]
    return "bell-outline", [0.88, 0.88, 0.90, 1]


class NotificationCard(RecycleDataViewBehavior, GlassCard):
    notification_id = StringProperty("")
    title = StringProperty("")
    message = StringProperty("")
    date_text = StringProperty("")
    icon = StringProperty("bell-outline")
    is_read = BooleanProperty(False)
    accent_color = ListProperty([0.95, 0.74, 0.12, 1])

    def refresh_view_attrs(self, rv, index, data):
        self.notification_id = str(data.get("notification_id") or data.get("id") or "")
        self.title = str(data.get("title") or "")
        self.message = str(data.get("message") or "")
        self.date_text = str(data.get("date_text") or data.get("created_at") or "")
        self.is_read = bool(data.get("is_read", False))
        icon, color = _style_for_type(data.get("type") or data.get("notification_type") or "")
        self.icon = str(data.get("icon") or icon)
        self.accent_color = list(data.get("accent_color") or color)
        return super().refresh_view_attrs(rv, index, data)
