from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivymd.uix.label import MDLabel


class BalanceCounter(MDLabel):
    """Animated currency label for the dashboard wallet balance."""

    current_value = NumericProperty(0.0)
    target_value = NumericProperty(0.0)
    currency_symbol = StringProperty("GH¢")
    highlight_color = ListProperty([0.95, 0.74, 0.12, 1])
    normal_color = ListProperty([0.98, 0.98, 0.98, 1])
    animation_duration = NumericProperty(1.15)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        self._sync_text(self.current_value)

    def on_target_value(self, *_args):
        self.animate_balance(self.target_value)

    def on_current_value(self, _instance, value):
        self._sync_text(value)

    def animate_balance(self, target):
        try:
            target_value = float(target or 0.0)
        except Exception:
            target_value = 0.0
        Animation.cancel_all(self, "current_value")
        self.theme_text_color = "Custom"
        self.text_color = list(self.highlight_color)
        Animation(current_value=target_value, duration=float(self.animation_duration or 1.15), transition="out_quad").start(self)
        Clock.schedule_once(lambda _dt: self._reset_highlight(), 0.18)

    def _sync_text(self, value):
        try:
            amount = float(value or 0.0)
        except Exception:
            amount = 0.0
        self.text = f"{self.currency_symbol} {amount:,.2f}"

    def _reset_highlight(self):
        self.text_color = list(self.normal_color)


try:
    from kivy.factory import Factory

    Factory.register("BalanceCounter", cls=BalanceCounter)
except Exception:
    pass

