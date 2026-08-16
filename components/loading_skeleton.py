from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.card import MDCard

from theme import CARD_PADDING, CARD_RADIUS, GLASS_BG, SURFACE


class LoadingSkeleton(MDCard):
    """Reusable loading placeholder with variant-specific layouts."""

    variant = StringProperty("default")
    rows = NumericProperty(3)
    animated = BooleanProperty(True)
    fade_duration = NumericProperty(0.18)
    pulse_duration = NumericProperty(0.75)

    def __init__(self, **kwargs):
        height = kwargs.get("height")
        super().__init__(**kwargs)
        self.size_hint_y = None
        self.radius = list(CARD_RADIUS)
        self.elevation = 0
        self.md_bg_color = list(SURFACE)
        self.line_color = list(GLASS_BG)
        self.padding = [CARD_PADDING, CARD_PADDING, CARD_PADDING, CARD_PADDING]
        self.opacity = 1
        self._body = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(10))
        self.add_widget(self._body)
        if height is not None:
            self.height = height
        else:
            self.height = self._default_height()
        self.bind(variant=self._rebuild, rows=self._rebuild)
        Clock.schedule_once(self._rebuild, 0)
        if self.animated:
            Clock.schedule_once(self._start_pulse, 0.1)

    def _default_height(self):
        variant = str(self.variant or "default").strip().lower()
        if variant == "wallet":
            return dp(128)
        if variant == "profile":
            return dp(112)
        if variant == "cards":
            return dp(148)
        if variant == "investments":
            return dp(124)
        if variant == "transactions":
            return dp(max(96, int(self.rows or 1) * 92))
        return dp(96)

    def _bar(self, width_hint=1.0, height=dp(12), radius=dp(6), opacity=0.12):
        return MDCard(
            size_hint=(max(0.08, min(1.0, float(width_hint))), None),
            height=height,
            radius=[radius, radius, radius, radius],
            md_bg_color=[1, 1, 1, opacity],
            elevation=0,
        )

    def _stack(self, widths, height=dp(12), spacing=dp(8)):
        row = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=spacing)
        for width in widths:
            row.add_widget(self._bar(width_hint=width, height=height))
        return row

    def _transaction_row(self):
        row = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing=dp(10))
        row.add_widget(self._bar(width_hint=0.12, height=dp(40), radius=dp(12), opacity=0.10))
        text_stack = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6))
        text_stack.add_widget(self._bar(width_hint=0.72, height=dp(12), opacity=0.14))
        text_stack.add_widget(self._bar(width_hint=0.52, height=dp(10), opacity=0.10))
        row.add_widget(text_stack)
        row.add_widget(self._bar(width_hint=0.22, height=dp(14), opacity=0.14))
        return row

    def _rebuild(self, *_args):
        self._body.clear_widgets()
        variant = str(self.variant or "default").strip().lower()
        row_count = max(1, int(self.rows or 1))

        if variant == "wallet":
            self.height = dp(128)
            top = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing=dp(10))
            top.add_widget(self._bar(width_hint=0.14, height=dp(44), radius=dp(16), opacity=0.10))
            top_text = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6))
            top_text.add_widget(self._bar(width_hint=0.48, height=dp(12), opacity=0.14))
            top_text.add_widget(self._bar(width_hint=0.36, height=dp(10), opacity=0.10))
            top.add_widget(top_text)
            self._body.add_widget(top)
            self._body.add_widget(self._bar(width_hint=0.72, height=dp(24), opacity=0.14))
            self._body.add_widget(self._bar(width_hint=0.42, height=dp(10), opacity=0.10))
            self._body.add_widget(self._bar(width_hint=0.52, height=dp(12), opacity=0.12))
            return

        if variant == "profile":
            self.height = dp(112)
            top = MDBoxLayout(orientation="horizontal", adaptive_height=True, spacing=dp(10))
            top.add_widget(self._bar(width_hint=0.16, height=dp(44), radius=dp(22), opacity=0.10))
            top_text = MDBoxLayout(orientation="vertical", adaptive_height=True, spacing=dp(6))
            top_text.add_widget(self._bar(width_hint=0.52, height=dp(12), opacity=0.14))
            top_text.add_widget(self._bar(width_hint=0.38, height=dp(10), opacity=0.10))
            top.add_widget(top_text)
            self._body.add_widget(top)
            self._body.add_widget(self._bar(width_hint=0.88, height=dp(12), opacity=0.12))
            self._body.add_widget(self._bar(width_hint=0.66, height=dp(12), opacity=0.10))
            return

        if variant == "cards":
            self.height = dp(148)
            self._body.add_widget(self._bar(width_hint=1.0, height=dp(76), radius=dp(20), opacity=0.12))
            self._body.add_widget(self._bar(width_hint=0.76, height=dp(12), opacity=0.14))
            self._body.add_widget(self._bar(width_hint=0.44, height=dp(12), opacity=0.10))
            return

        if variant == "investments":
            self.height = dp(124)
            self._body.add_widget(self._bar(width_hint=0.64, height=dp(14), opacity=0.14))
            self._body.add_widget(self._bar(width_hint=0.92, height=dp(16), opacity=0.12))
            self._body.add_widget(self._bar(width_hint=0.58, height=dp(12), opacity=0.10))
            self._body.add_widget(self._bar(width_hint=0.78, height=dp(12), opacity=0.10))
            return

        if variant == "transactions":
            self.height = dp(max(96, row_count * 92))
            for _index in range(row_count):
                self._body.add_widget(self._transaction_row())
            return

        self.height = dp(96)
        widths = [0.92, 0.66, 0.78, 0.58]
        for index in range(row_count):
            self._body.add_widget(self._bar(width_hint=widths[index % len(widths)], height=dp(12), opacity=0.12))

    def _start_pulse(self, *_args):
        if not self.animated:
            return
        Animation.cancel_all(self, "opacity")
        self.opacity = 0.82
        Animation(opacity=1.0, duration=float(self.pulse_duration or 0.75), t="in_out_sine").start(self)

    def fade_out(self, duration=None, on_complete=None):
        animation = Animation(opacity=0, duration=float(duration or self.fade_duration or 0.18), t="out_quad")
        if on_complete is not None:
            animation.bind(on_complete=lambda *_: on_complete())
        animation.start(self)
        self.disabled = True
        return animation

    def fade_in(self, duration=None):
        self.disabled = False
        self.opacity = 0
        animation = Animation(opacity=1, duration=float(duration or self.fade_duration or 0.18), t="out_quad")
        animation.start(self)
        return animation


try:
    from kivy.factory import Factory

    Factory.register("LoadingSkeleton", cls=LoadingSkeleton)
except Exception:
    pass
