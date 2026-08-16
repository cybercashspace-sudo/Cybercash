from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.icon import MDIcon
from kivymd.uix.label import MDLabel

try:
    from kivymd.uix.spinner import MDSpinner
except Exception:  # pragma: no cover - fallback for older builds
    try:
        from kivymd.uix.progressspinner import MDSpinner
    except Exception:  # pragma: no cover - final fallback
        MDSpinner = None

from theme import PRIMARY, TEXT_SECONDARY


class RefreshIndicator(MDBoxLayout):
    """Inline refresh status with a spinner or fallback icon."""

    active = BooleanProperty(True)
    text = StringProperty("Refreshing...")
    show_text = BooleanProperty(True)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = "horizontal"
        self.size_hint_y = None
        self.height = dp(24)
        self.spacing = dp(8)
        self._spinner = None
        self._label = MDLabel(
            text=self.text,
            theme_text_color="Custom",
            text_color=list(TEXT_SECONDARY),
            font_size="12sp",
            adaptive_height=True,
        )
        if MDSpinner is not None:
            self._spinner = MDSpinner(size_hint=(None, None), size=(dp(18), dp(18)), active=self.active)
        else:
            self._spinner = MDIcon(
                icon="refresh",
                theme_text_color="Custom",
                text_color=list(PRIMARY),
                font_size="18sp",
                size_hint=(None, None),
                size=(dp(18), dp(18)),
            )
        self.add_widget(self._spinner)
        self.add_widget(self._label)
        self.bind(active=self._sync, text=self._sync, show_text=self._sync)
        Clock.schedule_once(self._sync, 0)

    def _sync(self, *_args):
        if hasattr(self._spinner, "active"):
            self._spinner.active = bool(self.active)
        self._spinner.opacity = 1 if self.active else 0.45
        self._label.text = str(self.text or "")
        self._label.opacity = 1 if self.show_text else 0
        self._label.disabled = not bool(self.show_text)
        self.opacity = 1 if self.active else 0.65


try:
    from kivy.factory import Factory

    Factory.register("RefreshIndicator", cls=RefreshIndicator)
except Exception:
    pass
