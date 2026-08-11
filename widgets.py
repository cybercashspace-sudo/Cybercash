from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.properties import ListProperty, NumericProperty

from core.kivymd_compat import register_legacy_button_aliases
from theme import GLASS_BG, GLASS_BORDER, PRIMARY, PRIMARY_DARK, TEXT_PRIMARY

register_legacy_button_aliases()

from kivymd.uix.button import MDFillRoundFlatIconButton, MDRaisedButton  # noqa: E402
from kivymd.uix.card import MDCard  # noqa: E402


class GlassCard(MDCard):
    """
    Glassmorphism card used throughout CYBER CASH.
    """

    corner_radius = NumericProperty(dp(28))
    shadow_opacity = NumericProperty(0.22)
    shadow_offset = NumericProperty(dp(3))

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.radius = [dp(28)]
        self.elevation = 0
        self.md_bg_color = GLASS_BG
        self.line_color = GLASS_BORDER
        Clock.schedule_once(self._bind_shadow, 0)

    def _bind_shadow(self, *_):
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        self._update_canvas()

    def _update_canvas(self, *_):
        self.canvas.before.clear()

        with self.canvas.before:
            Color(0, 0, 0, self.shadow_opacity)
            RoundedRectangle(
                pos=(self.x, self.y - self.shadow_offset),
                size=self.size,
                radius=[self.corner_radius],
            )


class GoldButton(MDRaisedButton):
    """
    Primary gold action button.
    """

    base_color = ListProperty(PRIMARY)
    pressed_color = ListProperty(PRIMARY_DARK)
    text_color_value = ListProperty([0, 0, 0, 1])

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(56))
        super().__init__(**kwargs)
        self.style = "filled"
        self.radius = [dp(28)]
        self.elevation = 0
        self.md_bg_color = list(self.base_color)
        self.text_color = list(self.text_color_value)
        self.bind(on_press=self._press, on_release=self._release)

    def _press(self, *_):
        Animation(md_bg_color=list(self.pressed_color), d=0.08).start(self)

    def _release(self, *_):
        Animation(md_bg_color=list(self.base_color), d=0.12).start(self)


class SocialButton(MDFillRoundFlatIconButton):
    """
    Reusable social login button.
    """

    base_color = ListProperty([0.18, 0.18, 0.18, 1])
    pressed_color = ListProperty([0.24, 0.24, 0.24, 1])
    icon_tint = ListProperty(PRIMARY)
    text_tint = ListProperty(TEXT_PRIMARY)

    def __init__(self, **kwargs):
        kwargs.setdefault("size_hint_y", None)
        kwargs.setdefault("height", dp(52))
        super().__init__(**kwargs)
        self.radius = [dp(18)]
        self.elevation = 0
        self.style = "filled"
        self.md_bg_color = list(self.base_color)
        self.theme_text_color = "Custom"
        self.text_color = list(self.text_tint)
        self.theme_icon_color = "Custom"
        self.icon_color = list(self.icon_tint)
        self.bind(on_press=self._press, on_release=self._release)

    def _press(self, *_):
        Animation(md_bg_color=list(self.pressed_color), d=0.08).start(self)

    def _release(self, *_):
        Animation(md_bg_color=list(self.base_color), d=0.12).start(self)


__all__ = ["GlassCard", "GoldButton", "SocialButton"]
