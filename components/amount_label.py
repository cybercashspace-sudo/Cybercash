from __future__ import annotations

from kivy.properties import BooleanProperty, ListProperty, NumericProperty, StringProperty
from kivymd.uix.label import MDLabel

from theme import GREEN, RED, TEXT_PRIMARY, TEXT_SECONDARY


class AmountLabel(MDLabel):
    """Financial amount label with sign-aware color styling."""

    amount = NumericProperty(0.0)
    currency_symbol = StringProperty("GH₵")
    show_sign = BooleanProperty(True)
    positive_color = ListProperty(list(GREEN))
    negative_color = ListProperty(list(RED))
    neutral_color = ListProperty(list(TEXT_PRIMARY))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.theme_text_color = "Custom"
        self.bind(amount=self._sync)
        self._sync()

    def _sync(self, *_args):
        try:
            value = float(self.amount or 0.0)
        except Exception:
            value = 0.0
        sign = ""
        if self.show_sign:
            sign = "+" if value > 0 else "-" if value < 0 else ""
        amount_text = f"{abs(value):,.2f}"
        self.text = f"{sign}{self.currency_symbol} {amount_text}"
        if value > 0:
            self.text_color = list(self.positive_color or GREEN)
        elif value < 0:
            self.text_color = list(self.negative_color or RED)
        else:
            self.text_color = list(self.neutral_color or TEXT_PRIMARY)


try:
    from kivy.factory import Factory

    Factory.register("AmountLabel", cls=AmountLabel)
except Exception:
    pass
