from __future__ import annotations

from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty, ListProperty

from animations.home_animations import HomeAnimations, ShimmerEffect
from components.animated_card import AnimatedCard


class WalletCard(AnimatedCard):
    """Premium wallet card with a gold accent strip and shimmer."""

    accent_height = NumericProperty(dp(4))
    accent_color = ListProperty([1, 0.76, 0.12, 1])

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._shimmer = None
        self._accent_strip = None
        self.bind(pos=self._draw_accent, size=self._draw_accent)
        Clock.schedule_once(self._draw_accent, 0)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        Clock.schedule_once(lambda _dt: self.start_shimmer(), 0.15)

    def animate_in(self, *_args):
        HomeAnimations.pop_card(self, delay=0)

    def _draw_accent(self, *_args):
        try:
            if self._accent_strip is not None:
                return
            with self.canvas.before:
                Color(*self.accent_color)
                self._accent_strip = RoundedRectangle(
                    pos=(self.x, self.top - float(self.accent_height or dp(4))),
                    size=(self.width, float(self.accent_height or dp(4))),
                    radius=[dp(28), dp(28), 0, 0],
                )
        except Exception:
            return
        self._sync_accent()

    def _sync_accent(self, *_args):
        if self._accent_strip is None:
            return
        self._accent_strip.pos = (self.x, self.top - float(self.accent_height or dp(4)))
        self._accent_strip.size = (self.width, float(self.accent_height or dp(4)))

    def start_shimmer(self):
        if self._shimmer is None:
            self._shimmer = ShimmerEffect(self, speed=6.0, width=96.0, opacity=0.12)
        self._shimmer.start()

    def stop_shimmer(self):
        if self._shimmer is not None:
            self._shimmer.stop()

    def pulse(self):
        super().pulse()
        if self._shimmer is not None:
            self._shimmer.stop()
            Clock.schedule_once(lambda _dt: self.start_shimmer(), 0.22)


try:
    from kivy.factory import Factory

    Factory.register("WalletCard", cls=WalletCard)
except Exception:
    pass
