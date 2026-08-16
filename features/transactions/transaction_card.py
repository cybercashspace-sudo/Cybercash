from __future__ import annotations

from kivy.properties import BooleanProperty, ListProperty, StringProperty
from kivy.uix.recycleview.views import RecycleDataViewBehavior

from widgets import GlassCard


def _transaction_style(tx_type: str, status: str):
    kind = str(tx_type or "").strip().lower()
    state = str(status or "").strip().lower()
    if "withdraw" in kind:
        return "bank-transfer", [0.96, 0.67, 0.18, 1]
    if "transfer" in kind:
        return "swap-horizontal", [0.60, 0.78, 1.00, 1]
    if "bitcoin" in kind or "btc" in kind:
        return "bitcoin", [0.95, 0.74, 0.12, 1]
    if "deposit" in kind:
        return "cash-plus", [0.50, 0.88, 0.60, 1]
    if "pending" in state:
        return "clock-outline", [0.96, 0.80, 0.18, 1]
    if "failed" in state:
        return "close-circle-outline", [0.95, 0.42, 0.42, 1]
    return "receipt-text-outline", [0.80, 0.82, 0.86, 1]


class TransactionCard(RecycleDataViewBehavior, GlassCard):
    transaction_id = StringProperty("")
    title = StringProperty("")
    amount_text = StringProperty("")
    status_text = StringProperty("")
    date_text = StringProperty("")
    description = StringProperty("")
    icon = StringProperty("receipt-text-outline")
    accent_color = ListProperty([0.95, 0.74, 0.12, 1])
    status_color = ListProperty([0.80, 0.82, 0.86, 1])
    is_read = BooleanProperty(True)

    def refresh_view_attrs(self, rv, index, data):
        self.transaction_id = str(data.get("transaction_id") or data.get("id") or "")
        self.title = str(data.get("title") or data.get("type") or "Transaction")
        self.amount_text = str(data.get("amount_text") or data.get("amount") or "0")
        self.status_text = str(data.get("status_text") or data.get("status") or "")
        self.date_text = str(data.get("date_text") or data.get("created_at") or "")
        self.description = str(data.get("description") or "")
        self.is_read = bool(data.get("is_read", True))
        icon, color = _transaction_style(data.get("type") or data.get("transaction_type") or "", data.get("status") or "")
        self.icon = str(data.get("icon") or icon)
        self.accent_color = list(data.get("accent_color") or color)
        self.status_color = list(data.get("status_color") or color)
        return super().refresh_view_attrs(rv, index, data)
