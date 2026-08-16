from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.icon import MDIcon
from kivymd.uix.label import MDLabel

from theme import TEXT_PRIMARY, TEXT_SECONDARY


class EmptyState(MDBoxLayout):
    """Reusable empty-state illustration and copy."""

    icon = StringProperty("inbox-outline")
    title = StringProperty("Nothing here yet")
    message = StringProperty("We will show items here once they arrive.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "vertical"
        self.size_hint_y = None
        self.adaptive_height = True
        self.padding = [dp(16), dp(16), dp(16), dp(16)]
        self.spacing = dp(10)

        self._icon = MDIcon(
            icon=self.icon,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="44sp",
            halign="center",
            size_hint_y=None,
            height=dp(54),
        )
        self._title = MDLabel(
            text=self.title,
            theme_text_color="Custom",
            text_color=list(TEXT_PRIMARY),
            bold=True,
            halign="center",
            adaptive_height=True,
        )
        self._message = MDLabel(
            text=self.message,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            halign="center",
            adaptive_height=True,
        )

        self.add_widget(self._icon)
        self.add_widget(self._title)
        self.add_widget(self._message)
        self.bind(icon=self._sync, title=self._sync, message=self._sync)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args):
        self._icon.icon = str(self.icon or "inbox-outline")
        self._title.text = str(self.title or "")
        self._message.text = str(self.message or "")
        self.height = self.minimum_height


try:
    from kivy.factory import Factory

    Factory.register("EmptyState", cls=EmptyState)
except Exception:
    pass
