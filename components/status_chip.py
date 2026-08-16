from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard
from kivymd.uix.icon import MDIcon
from kivymd.uix.label import MDLabel

from theme import ERROR, GLASS_BG, INFO, PRIMARY, PILL_RADIUS, SUCCESS, TEXT_PRIMARY, WARNING


class StatusChip(MDCard):
    """Pill-shaped status badge with a single text label."""

    text = StringProperty("Status")
    status = StringProperty("neutral")
    icon = StringProperty("information-outline")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.height = dp(30)
        self.radius = list(PILL_RADIUS)
        self.elevation = 0
        self.padding = [dp(10), 0, dp(10), 0]

        self._content = MDBoxLayout(orientation="horizontal", spacing=dp(6), adaptive_height=True)
        self._icon = MDIcon(
            icon=self.icon,
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            font_size="16sp",
            size_hint=(None, None),
            size=(dp(16), dp(16)),
            pos_hint={"center_y": 0.5},
        )
        self._label = MDLabel(
            text=self.text,
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            font_size="12sp",
            bold=True,
            size_hint_x=None,
            adaptive_height=True,
        )
        self._content.add_widget(self._icon)
        self._content.add_widget(self._label)
        self.add_widget(self._content)
        self.bind(text=self._sync, status=self._sync, icon=self._sync)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args):
        status = str(self.status or "neutral").strip().lower()
        palette = {
            "success": (SUCCESS, [0.07, 0.25, 0.16, 1]),
            "warning": (WARNING, [0.24, 0.19, 0.05, 1]),
            "error": (ERROR, [0.25, 0.10, 0.10, 1]),
            "info": (INFO, [0.06, 0.18, 0.23, 1]),
            "primary": (PRIMARY, [0.16, 0.13, 0.03, 1]),
            "neutral": (GLASS_BG, [1, 1, 1, 0.08]),
        }
        icon_color, background = palette.get(status, palette["neutral"])
        self.md_bg_color = list(background)
        self._icon.text_color = list(icon_color)
        self._icon.icon = str(self.icon or "information-outline")
        self._label.text = str(self.text or "")
        self.height = dp(30)


try:
    from kivy.factory import Factory

    Factory.register("StatusChip", cls=StatusChip)
except Exception:
    pass
