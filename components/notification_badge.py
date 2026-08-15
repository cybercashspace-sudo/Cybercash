from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.label import MDLabel

from theme import PILL_RADIUS, PRIMARY, TEXT_PRIMARY


class NotificationBadge(MDCard):
    """Small count badge for unread notifications."""

    count = NumericProperty(0)
    max_count = NumericProperty(99)
    visible = BooleanProperty(True)
    badge_text = StringProperty("0")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.size = (dp(22), dp(22))
        self.radius = list(PILL_RADIUS)
        self.elevation = 0
        self.md_bg_color = list(PRIMARY)
        self._label = MDLabel(
            text="0",
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            halign="center",
            valign="middle",
            bold=True,
            font_size="11sp",
        )
        container = MDBoxLayout(padding=0)
        container.add_widget(self._label)
        self.add_widget(container)
        self.bind(count=self._sync, visible=self._sync)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args):
        count = max(0, int(self.count or 0))
        self.badge_text = f"{min(count, int(self.max_count or 99))}"
        self._label.text = self.badge_text
        self.opacity = 1 if self.visible and count > 0 else 0
        self.disabled = not bool(self.visible and count > 0)


try:
    from kivy.factory import Factory

    Factory.register("NotificationBadge", cls=NotificationBadge)
except Exception:
    pass

