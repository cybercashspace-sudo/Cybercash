from __future__ import annotations

from kivy.metrics import dp
from kivy.properties import NumericProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard

from theme import CARD_PADDING, CARD_RADIUS, SURFACE, TEXT_SECONDARY


class LoadingSkeleton(MDCard):
    """Simple reusable loading placeholder."""

    rows = NumericProperty(3)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.height = kwargs.get("height", dp(96))
        self.radius = list(CARD_RADIUS)
        self.elevation = 0
        self.md_bg_color = list(SURFACE)
        self.padding = [CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING]
        self._body = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(10))
        self.add_widget(self._body)
        self.bind(rows=self._rebuild)
        self._rebuild()

    def _rebuild(self, *_args):
        self._body.clear_widgets()
        widths = [0.92, 0.66, 0.78, 0.58]
        row_total = max(1, int(self.rows or 1))
        for index in range(row_total):
            bar = MDCard(
                size_hint=(widths[index % len(widths)], None),
                height=dp(12),
                radius=[dp(6), dp(6), dp(6), dp(6)],
                md_bg_color=[1, 1, 1, 0.10],
                elevation=0,
            )
            self._body.add_widget(bar)


try:
    from kivy.factory import Factory

    Factory.register("LoadingSkeleton", cls=LoadingSkeleton)
except Exception:
    pass

