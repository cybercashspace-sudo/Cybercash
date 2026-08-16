from __future__ import annotations

try:
    from kivy.core.clipboard import Clipboard
except Exception:  # pragma: no cover - clipboard is optional on some runtimes
    Clipboard = None

from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import BooleanProperty, ListProperty, NumericProperty, ObjectProperty, OptionProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.button import MDIconButton
from kivymd.uix.label import MDLabel
from kivy.uix.widget import Widget

from animations.home_animations import HomeAnimations, ShimmerEffect
from components.animated_card import AnimatedCard
from components.balance_counter import BalanceCounter
from core.feedback_engine import tap_feedback
from theme import TEXT_PRIMARY, TEXT_SECONDARY


class WalletCard(AnimatedCard):
    """Premium wallet summary card with optional summary mode and shimmer."""

    content_mode = OptionProperty("custom", options=("custom", "summary"))
    balance = NumericProperty(0.0)
    currency = StringProperty("GH\u20B5")
    account_name = StringProperty("")
    wallet_id = StringProperty("")
    account_number = StringProperty("")
    is_hidden = BooleanProperty(False)
    last_updated = StringProperty("")
    loading = BooleanProperty(False)
    show_actions = BooleanProperty(True)
    show_copy_button = BooleanProperty(True)
    show_visibility_button = BooleanProperty(True)
    show_refresh_button = BooleanProperty(True)
    balance_precision = NumericProperty(2)
    accent_color = ListProperty([1, 0.76, 0.12, 1])
    balance_color = ListProperty(list(TEXT_PRIMARY))
    secondary_text_color = ListProperty(list(TEXT_SECONDARY))
    refresh_callback = ObjectProperty(None, allownone=True)
    pull_to_refresh_callback = ObjectProperty(None, allownone=True)
    copy_callback = ObjectProperty(None, allownone=True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self._shimmer = None
        self._accent_strip = None
        self._summary_root = None
        self._name_label = None
        self._wallet_label = None
        self._updated_label = None
        self._balance_counter = None
        self._hidden_balance_label = None
        self._action_row = None
        self._toggle_button = None
        self._copy_button = None
        self._refresh_button = None

        self.bind(
            pos=self._sync_accent,
            size=self._sync_accent,
            balance=self._sync_summary,
            currency=self._sync_summary,
            account_name=self._sync_summary,
            wallet_id=self._sync_summary,
            account_number=self._sync_summary,
            is_hidden=self._sync_summary,
            last_updated=self._sync_summary,
            loading=self._sync_loading,
            show_actions=self._sync_summary,
            show_copy_button=self._sync_summary,
            show_visibility_button=self._sync_summary,
            show_refresh_button=self._sync_summary,
            content_mode=self._sync_layout,
        )
        Clock.schedule_once(self._initialize_card, 0)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        Clock.schedule_once(self._initialize_card, 0)

    def animate_in(self, *_args):
        HomeAnimations.pop_card(self, delay=0)

    def _initialize_card(self, *_args):
        self._draw_accent()
        self._sync_layout()

    def _draw_accent(self, *_args):
        if self._accent_strip is not None:
            self._sync_accent()
            return
        try:
            with self.canvas.before:
                Color(*self.accent_color)
                self._accent_strip = RoundedRectangle(
                    pos=(self.x, self.top - dp(4)),
                    size=(self.width, dp(4)),
                    radius=[dp(28), dp(28), 0, 0],
                )
        except Exception:
            return
        self._sync_accent()

    def _sync_accent(self, *_args):
        if self._accent_strip is None:
            return
        try:
            self._accent_strip.pos = (self.x, self.top - dp(4))
            self._accent_strip.size = (self.width, dp(4))
        except Exception:
            pass

    def _sync_layout(self, *_args):
        if self.content_mode == "summary":
            self._ensure_summary_layout()
            self._sync_summary()
            return

        self._remove_summary_layout()
        self.stop_shimmer()

    def _ensure_summary_layout(self):
        if self._summary_root is not None:
            return

        self.clear_widgets()
        self._summary_root = MDBoxLayout(
            orientation="vertical",
            spacing=dp(10),
            padding=[dp(16), dp(16), dp(16), dp(16)],
            adaptive_height=True,
        )

        header = MDBoxLayout(orientation="vertical", spacing=dp(2), adaptive_height=True)
        self._name_label = MDLabel(
            text=self._display_name(),
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            bold=True,
            font_size="18sp",
            adaptive_height=True,
            shorten=True,
            shorten_from="right",
        )
        self._wallet_label = MDLabel(
            text=self._wallet_identifier_text(),
            theme_text_color="Custom",
            text_color=list(self.secondary_text_color),
            font_size="12sp",
            adaptive_height=True,
            shorten=True,
            shorten_from="right",
        )
        self._updated_label = MDLabel(
            text=self._last_updated_text(),
            theme_text_color="Custom",
            text_color=list(self.secondary_text_color),
            font_size="11sp",
            adaptive_height=True,
            shorten=True,
            shorten_from="right",
        )
        header.add_widget(self._name_label)
        header.add_widget(self._wallet_label)
        header.add_widget(self._updated_label)

        balance_caption = MDLabel(
            text="Available balance",
            theme_text_color="Custom",
            text_color=list(self.secondary_text_color),
            font_size="11sp",
            adaptive_height=True,
        )
        self._balance_counter = BalanceCounter(
            text="",
            theme_text_color="Custom",
            text_color=list(self.balance_color),
            font_size="32sp",
            bold=True,
            adaptive_height=True,
        )
        self._balance_counter.currency_symbol = self.currency
        self._balance_counter.precision = int(self.balance_precision or 2)
        self._balance_counter.highlight_color = list(self.accent_color)
        self._balance_counter.normal_color = list(self.balance_color)

        self._hidden_balance_label = MDLabel(
            text=self._masked_balance(),
            theme_text_color="Custom",
            text_color=list(self.balance_color),
            font_size="32sp",
            bold=True,
            adaptive_height=True,
            opacity=0,
        )

        balance_stack = MDBoxLayout(
            orientation="vertical",
            spacing=dp(4),
            adaptive_height=True,
        )
        balance_stack.add_widget(balance_caption)
        balance_stack.add_widget(self._balance_counter)
        balance_stack.add_widget(self._hidden_balance_label)

        self._action_row = MDBoxLayout(
            orientation="horizontal",
            spacing=dp(6),
            adaptive_height=True,
            size_hint_y=None,
            height=dp(40),
        )
        self._toggle_button = MDIconButton(
            icon="eye-off" if self.is_hidden else "eye",
            theme_icon_color="Custom",
            icon_color=list(self.accent_color),
            on_release=lambda *_: self.toggle_balance_visibility(),
        )
        self._copy_button = MDIconButton(
            icon="content-copy",
            theme_icon_color="Custom",
            icon_color=list(self.accent_color),
            on_release=lambda *_: self.copy_wallet_or_account_number(),
        )
        self._refresh_button = MDIconButton(
            icon="refresh",
            theme_icon_color="Custom",
            icon_color=list(self.accent_color),
            on_release=lambda *_: self.refresh(),
        )
        self._action_row.add_widget(self._toggle_button)
        self._action_row.add_widget(self._copy_button)
        self._action_row.add_widget(self._refresh_button)
        self._action_row.add_widget(Widget())

        self._summary_root.add_widget(header)
        self._summary_root.add_widget(balance_stack)
        self._summary_root.add_widget(self._action_row)
        self.add_widget(self._summary_root)

    def _remove_summary_layout(self):
        if self._summary_root is None:
            return
        try:
            if self._summary_root.parent is self:
                self.remove_widget(self._summary_root)
        except Exception:
            pass
        self._summary_root = None
        self._name_label = None
        self._wallet_label = None
        self._updated_label = None
        self._balance_counter = None
        self._hidden_balance_label = None
        self._action_row = None
        self._toggle_button = None
        self._copy_button = None
        self._refresh_button = None

    def _sync_summary(self, *_args):
        if self.content_mode != "summary":
            return
        if self._summary_root is None:
            self._ensure_summary_layout()
        if self._summary_root is None:
            return

        self._name_label.text = self._display_name()
        self._wallet_label.text = self._wallet_identifier_text()
        self._updated_label.text = self._last_updated_text()

        self._toggle_button.icon = "eye-off" if self.is_hidden else "eye"
        self._toggle_button.icon_color = list(self.accent_color)
        self._copy_button.icon_color = list(self.accent_color)
        self._refresh_button.icon_color = list(self.accent_color)
        self._copy_button.disabled = not bool(self.show_copy_button and self._copy_target())
        self._toggle_button.disabled = not bool(self.show_visibility_button)
        self._refresh_button.disabled = not bool(self.show_refresh_button)
        self._action_row.opacity = 1 if self.show_actions else 0
        self._action_row.disabled = not self.show_actions

        if self.is_hidden:
            self._balance_counter.opacity = 0
            self._hidden_balance_label.opacity = 1
            self._hidden_balance_label.text = self._masked_balance()
        else:
            self._balance_counter.opacity = 1
            self._hidden_balance_label.opacity = 0
            self._balance_counter.currency_symbol = self.currency
            self._balance_counter.precision = int(self.balance_precision or 2)
            self._balance_counter.highlight_color = list(self.accent_color)
            self._balance_counter.normal_color = list(self.balance_color)
            self._balance_counter.animate_balance(self.balance)

        self._sync_loading()

    def _sync_loading(self, *_args):
        if self.loading:
            self.start_shimmer()
            if self._summary_root is not None:
                self._summary_root.opacity = 0.86
            return

        self.stop_shimmer()
        if self._summary_root is not None:
            self._summary_root.opacity = 1.0

    def _display_name(self):
        return str(self.account_name or "Wallet summary")

    def _copy_target(self):
        return str(self.account_number or self.wallet_id or "").strip()

    def _wallet_identifier_text(self):
        target = self._copy_target()
        if not target:
            return "Account number not set"
        return f"Wallet / account: {target}"

    def _last_updated_text(self):
        stamp = str(self.last_updated or "").strip()
        if not stamp:
            return "Last updated just now"
        return f"Last updated {stamp}"

    def _masked_balance(self):
        return f"{self.currency} \u2022\u2022\u2022\u2022\u2022\u2022"

    def set_balance(self, value, *, animate: bool = True):
        try:
            self.balance = float(value or 0.0)
        except Exception:
            self.balance = 0.0
        if not animate:
            self._sync_summary()

    def animate_balance(self, value):
        self.set_balance(value, animate=True)

    def toggle_balance_visibility(self):
        self.is_hidden = not bool(self.is_hidden)
        self._sync_summary()

    def show_balance(self):
        self.is_hidden = False
        self._sync_summary()

    def hide_balance(self):
        self.is_hidden = True
        self._sync_summary()

    def copy_wallet_or_account_number(self):
        target = self._copy_target()
        if not target:
            return
        tap_feedback()
        if callable(self.copy_callback):
            try:
                self.copy_callback(target)
            except TypeError:
                self.copy_callback()
            return
        if Clipboard is not None:
            try:
                Clipboard.copy(target)
            except Exception:
                pass

    def refresh(self):
        callback = self.refresh_callback or self.pull_to_refresh_callback
        if callable(callback):
            tap_feedback()
            try:
                callback()
            except TypeError:
                callback(self)

    def trigger_pull_to_refresh(self):
        callback = self.pull_to_refresh_callback or self.refresh_callback
        if callable(callback):
            tap_feedback()
            try:
                callback()
            except TypeError:
                callback(self)

    def start_shimmer(self):
        if self._shimmer is None:
            self._shimmer = ShimmerEffect(self, speed=6.0, width=96.0, opacity=0.12)
        self._shimmer.start()

    def stop_shimmer(self):
        if self._shimmer is not None:
            self._shimmer.stop()

    def pulse(self):
        super().pulse()
        if self._shimmer is not None:
            self._shimmer.stop()
            Clock.schedule_once(lambda _dt: self.start_shimmer(), 0.22)


try:
    from kivy.factory import Factory

    Factory.register("WalletCard", cls=WalletCard)
except Exception:
    pass
