from __future__ import annotations

from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, StringProperty
from kivymd.uix.button import MDRaisedButton

from core.animation_helpers import AnimationManager
from theme import BUTTON_RADIUS, GLASS_BORDER, PRIMARY, RED, SURFACE, TEXT_PRIMARY, TEXT_SECONDARY


class AppButton(MDRaisedButton):
    """Shared action button with consistent color, radius, and loading behavior."""

    variant = StringProperty("primary")
    loading = BooleanProperty(False)
    loading_text = StringProperty("Loading...")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._original_text = str(getattr(self, "text", "") or "")
        self._disabled_before_loading = bool(getattr(self, "disabled", False))
        self.size_hint_y = None
        if not float(getattr(self, "height", 0) or 0):
            self.height = dp(52)
        self.radius = list(BUTTON_RADIUS)
        self.elevation = 0
        self.bind(variant=self._apply_variant, loading=self._apply_loading)
        self.bind(on_press=self._animate_press)
        Clock.schedule_once(self._apply_variant, 0)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        self._original_text = str(getattr(self, "text", "") or self._original_text)
        self._apply_variant()
        self._apply_loading()

    def _apply_variant(self, *_args):
        variant = str(self.variant or "primary").strip().lower()
        self.line_color = list(GLASS_BORDER)
        if variant == "secondary":
            self.md_bg_color = list(SURFACE)
            self.text_color = list(TEXT_PRIMARY)
        elif variant == "danger":
            self.md_bg_color = list(RED)
            self.text_color = [0, 0, 0, 1]
        elif variant == "ghost":
            self.md_bg_color = [0, 0, 0, 0]
            self.line_color = list(PRIMARY)
            self.text_color = list(PRIMARY)
        else:
            self.md_bg_color = list(PRIMARY)
            self.text_color = [0, 0, 0, 1]

    def _apply_loading(self, *_args):
        if self.loading:
            self._disabled_before_loading = bool(self.disabled)
            self.disabled = True
            self.opacity = 0.72
            if self.loading_text:
                self.text = str(self.loading_text)
            return

        self.disabled = bool(self._disabled_before_loading)
        self.opacity = 1.0
        if self._original_text:
            self.text = self._original_text

    def _animate_press(self, *_args):
        if self.loading or self.disabled:
            return
        AnimationManager.pulse(self, shrink=0.97, duration=0.08)


try:
    from kivy.factory import Factory

    Factory.register("AppButton", cls=AppButton)
except Exception:
    pass
