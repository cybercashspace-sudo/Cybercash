from __future__ import annotations

from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty
from kivymd.uix.button import MDIconButton

from theme import PRIMARY, TEXT_PRIMARY


class AppIconButton(MDIconButton):
    """Shared icon-only action button."""

    icon_color = ListProperty(list(PRIMARY))
    size_dp = NumericProperty(44)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.size_hint = (None, None)
        self.font_size = "24sp"
        self.theme_text_color = "Custom"
        self.text_color = list(self.icon_color or PRIMARY)
        self.ripple_scale = 0.95
        self.bind(icon_color=self._sync_color, size_dp=self._sync_size)
        self._sync_size()
        self._sync_color()

    def _sync_color(self, *_args):
        self.text_color = list(self.icon_color or TEXT_PRIMARY)

    def _sync_size(self, *_args):
        size = dp(float(self.size_dp or 44))
        self.size = (size, size)


try:
    from kivy.factory import Factory

    Factory.register("AppIconButton", cls=AppIconButton)
except Exception:
    pass
