from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivy.uix.recycleview.views import RecycleDataViewBehavior
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.icon import MDIcon
from kivymd.uix.label import MDLabel
from kivy.uix.widget import Widget

from components.amount_label import AmountLabel
from components.status_chip import StatusChip
from theme import BTC, ERROR, INFO, PRIMARY, SUCCESS, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY, WARNING
from widgets import GlassCard


def _humanize(value: str, fallback: str = "Transaction") -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text.replace("_", " ").replace("-", " ").title()


def _normalize_type(tx_type: str) -> str:
    return str(tx_type or "").strip().lower()


def _normalize_status(status: str) -> str:
    return str(status or "").strip().lower()


def _style_for_type(tx_type: str):
    kind = _normalize_type(tx_type)
    if "deposit" in kind:
        return "cash-plus", list(SUCCESS)
    if "transfer" in kind:
        return "swap-horizontal", list(INFO)
    if "withdraw" in kind:
        return "bank-transfer", list(WARNING)
    if "airtime" in kind:
        return "cellphone", [0.38, 0.78, 0.96, 1]
    if "data bundle" in kind or "bundle" in kind or kind == "data":
        return "sim-outline", [0.54, 0.72, 0.98, 1]
    if "bitcoin" in kind or "btc" in kind:
        return "bitcoin", list(BTC)
    if "investment" in kind:
        return "chart-line", list(PRIMARY)
    if "loan" in kind:
        return "hand-coin-outline", [0.93, 0.62, 0.25, 1]
    if "virtual card" in kind or "card" in kind:
        return "credit-card-outline", [0.60, 0.80, 1.00, 1]
    return "receipt-text-outline", list(TEXT_SECONDARY)


def _style_for_status(status: str):
    state = _normalize_status(status)
    if state in {"completed", "complete", "done", "success", "verified"}:
        return "success", "check-circle-outline", list(SUCCESS)
    if state in {"pending", "queued"}:
        return "warning", "clock-outline", list(WARNING)
    if state in {"processing", "in-progress", "progress"}:
        return "info", "progress-clock", list(INFO)
    if state in {"failed", "failure", "error", "rejected"}:
        return "error", "close-circle-outline", list(ERROR)
    if state in {"cancelled", "canceled"}:
        return "neutral", "cancel", list(TEXT_SECONDARY)
    return "neutral", "information-outline", list(TEXT_SECONDARY)


class TransactionCard(RecycleDataViewBehavior, GlassCard):
    """Reusable transaction tile with type-aware icon and status handling."""

    transaction_id = StringProperty("")
    title = StringProperty("")
    amount_text = StringProperty("")
    status_text = StringProperty("")
    date_text = StringProperty("")
    description = StringProperty("")
    transaction_type = StringProperty("")
    status = StringProperty("")
    direction = StringProperty("")
    currency_symbol = StringProperty("GH\u20B5")
    amount_value = NumericProperty(0.0)
    icon = StringProperty("receipt-text-outline")
    accent_color = ListProperty(list(TEXT_SECONDARY))
    status_color = ListProperty(list(TEXT_SECONDARY))
    status_chip_status = StringProperty("neutral")
    status_chip_icon = StringProperty("information-outline")
    is_read = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = dp(92)
        self.radius = [dp(18)]
        self.elevation = 0
        self.md_bg_color = list(SURFACE)
        self.line_color = [1, 1, 1, 0.08]
        self.padding = [dp(12), dp(10), dp(12), dp(10)]

        self._fallback_root = None
        self._icon_card = None
        self._icon = None
        self._title_label = None
        self._description_label = None
        self._date_label = None
        self._amount_label = None
        self._status_chip = None

        self.bind(
            transaction_type=self._sync_fallback,
            status=self._sync_fallback,
            title=self._sync_fallback,
            amount_value=self._sync_fallback,
            amount_text=self._sync_fallback,
            status_text=self._sync_fallback,
            date_text=self._sync_fallback,
            description=self._sync_fallback,
            icon=self._sync_fallback,
            accent_color=self._sync_fallback,
            status_color=self._sync_fallback,
            status_chip_status=self._sync_fallback,
            status_chip_icon=self._sync_fallback,
            currency_symbol=self._sync_fallback,
            is_read=self._sync_fallback,
        )
        Clock.schedule_once(self._ensure_layout, 0)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        Clock.schedule_once(self._ensure_layout, 0)

    def refresh_view_attrs(self, rv, index, data):
        self.apply_data(data)
        return super().refresh_view_attrs(rv, index, data)

    def apply_data(self, data: dict | None):
        payload = dict(data or {})
        self.transaction_id = str(payload.get("transaction_id") or payload.get("id") or "")
        self.transaction_type = str(payload.get("transaction_type") or payload.get("type") or "")
        self.status = str(payload.get("status") or payload.get("state") or "")
        self.status_text = str(payload.get("status_text") or _humanize(self.status, "Pending"))
        self.title = str(payload.get("title") or _humanize(self.transaction_type, "Transaction"))
        self.description = str(payload.get("description") or payload.get("subtitle") or "")
        self.date_text = str(payload.get("date_text") or payload.get("created_at") or payload.get("timestamp") or "")
        self.direction = str(payload.get("direction") or payload.get("flow") or "").strip().lower()
        self.currency_symbol = str(payload.get("currency_symbol") or payload.get("currency") or self.currency_symbol or "GH\u20B5")

        raw_amount = self._coerce_amount(payload.get("amount"))
        signed_amount = self._signed_amount(raw_amount, self.direction, self.transaction_type)
        self.amount_value = signed_amount
        self.amount_text = str(
            payload.get("amount_text")
            or self._format_amount_text(signed_amount, self.currency_symbol)
        )

        icon, accent = _style_for_type(self.transaction_type)
        status_chip_status, status_chip_icon, status_color = _style_for_status(self.status or self.status_text)
        self.icon = str(payload.get("icon") or icon)
        self.accent_color = list(payload.get("accent_color") or accent)
        self.status_color = list(payload.get("status_color") or status_color)
        self.status_chip_status = str(payload.get("status_chip_status") or status_chip_status)
        self.status_chip_icon = str(payload.get("status_chip_icon") or status_chip_icon)
        self.is_read = bool(payload.get("is_read", True))
        self._sync_fallback()

    def _coerce_amount(self, value):
        try:
            return float(value or 0.0)
        except Exception:
            return 0.0

    def _signed_amount(self, amount: float, direction: str, tx_type: str) -> float:
        kind = _normalize_type(tx_type)
        flow = str(direction or "").strip().lower()
        if amount == 0:
            return 0.0
        if amount < 0:
            return amount
        if flow in {"debit", "out", "outgoing", "sent", "withdrawal"}:
            return -abs(amount)
        if flow in {"credit", "in", "incoming", "received", "deposit"}:
            return abs(amount)
        if "withdraw" in kind or "loan" in kind or "send" in kind or "airtime" in kind or "data" in kind:
            return -abs(amount)
        return abs(amount)

    def _format_amount_text(self, amount: float, currency_symbol: str) -> str:
        sign = "+" if amount > 0 else "-" if amount < 0 else ""
        prefix = f"{sign} " if sign else ""
        return f"{prefix}{currency_symbol} {abs(amount):,.2f}"

    def _ensure_layout(self, *_args):
        if self.children:
            self._sync_fallback()
            return
        if self._fallback_root is None:
            self._build_fallback_layout()
        self._sync_fallback()

    def _build_fallback_layout(self):
        self.clear_widgets()
        self._fallback_root = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            adaptive_height=True,
        )

        self._icon_card = MDCard(
            size_hint=(None, None),
            size=(dp(42), dp(42)),
            radius=[dp(14), dp(14), dp(14), dp(14)],
            md_bg_color=list(self.accent_color),
            elevation=0,
        )
        self._icon = MDIcon(
            icon=self.icon,
            theme_text_color="Custom",
            text_color=[0.05, 0.05, 0.05, 1],
            pos_hint={"center_x": 0.5, "center_y": 0.5},
        )
        self._icon_card.add_widget(self._icon)

        text_stack = MDBoxLayout(orientation="vertical", spacing=dp(2), adaptive_height=True)
        self._title_label = MDLabel(
            text=self.title,
            bold=True,
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            shorten=True,
            shorten_from="right",
            adaptive_height=True,
        )
        self._description_label = MDLabel(
            text=self.description,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="12sp",
            shorten=True,
            shorten_from="right",
            adaptive_height=True,
        )
        self._date_label = MDLabel(
            text=self.date_text,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="11sp",
            shorten=True,
            shorten_from="right",
            adaptive_height=True,
        )
        text_stack.add_widget(self._title_label)
        text_stack.add_widget(self._description_label)
        text_stack.add_widget(self._date_label)

        right_stack = MDBoxLayout(
            orientation="vertical",
            spacing=dp(6),
            adaptive_height=True,
            size_hint_x=None,
            width=dp(140),
        )
        self._amount_label = AmountLabel(
            amount=self.amount_value,
            currency_symbol=self.currency_symbol,
            show_sign=True,
            theme_text_color="Custom",
            text_color=list(self.status_color),
            font_size="14sp",
            bold=True,
            halign="right",
            adaptive_height=True,
        )
        self._status_chip = StatusChip(
            text=self.status_text,
            status=self.status_chip_status,
            icon=self.status_chip_icon,
        )
        right_stack.add_widget(self._amount_label)
        right_stack.add_widget(self._status_chip)

        self._fallback_root.add_widget(self._icon_card)
        self._fallback_root.add_widget(text_stack)
        self._fallback_root.add_widget(Widget())
        self._fallback_root.add_widget(right_stack)
        self.add_widget(self._fallback_root)

    def _sync_fallback(self, *_args):
        if self._fallback_root is None:
            return

        if self.children and self._fallback_root not in self.children:
            return

        self.md_bg_color = [0.13, 0.13, 0.14, 1] if not self.is_read else list(SURFACE)
        self.line_color = list(self.accent_color)

        if self._icon_card is not None:
            self._icon_card.md_bg_color = list(self.accent_color)
        if self._icon is not None:
            self._icon.icon = str(self.icon or "receipt-text-outline")
        if self._title_label is not None:
            self._title_label.text = self.title or _humanize(self.transaction_type, "Transaction")
        if self._description_label is not None:
            self._description_label.text = self.description or ""
        if self._date_label is not None:
            self._date_label.text = self.date_text or ""
        if self._amount_label is not None:
            self._amount_label.amount = self.amount_value
            self._amount_label.currency_symbol = self.currency_symbol
            self._amount_label.text_color = list(self.status_color)
        if self._status_chip is not None:
            self._status_chip.text = self.status_text or _humanize(self.status, "Pending")
            self._status_chip.status = self.status_chip_status
            self._status_chip.icon = self.status_chip_icon


try:
    from kivy.factory import Factory

    Factory.register("TransactionCard", cls=TransactionCard)
except Exception:
    pass
