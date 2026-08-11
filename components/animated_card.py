from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty

from core.fintech_widgets import GradientMDCard


class AnimatedCard(GradientMDCard):
    """Gradient card with a small entrance animation."""

    entrance_delay = NumericProperty(0.0)
    entrance_offset = NumericProperty(dp(12))
    entrance_duration = NumericProperty(0.45)

    def on_kv_post(self, _base_widget):
        super().on_kv_post(_base_widget)
        Clock.schedule_once(self.animate_in, float(self.entrance_delay or 0.0))

    def animate_in(self, *_args):
        origin_y = getattr(self, "_cybercash_origin_y", self.y)
        self._cybercash_origin_y = origin_y
        self.opacity = 0
        self.y = origin_y - float(self.entrance_offset or 0)
        Animation(
            opacity=1,
            y=origin_y,
            duration=float(self.entrance_duration or 0.45),
            transition="out_back",
        ).start(self)

    def pulse(self):
        origin_y = getattr(self, "_cybercash_origin_y", self.y)
        Animation(y=origin_y + dp(4), duration=0.08, transition="out_quad").start(self)
        Animation(y=origin_y, duration=0.14, transition="out_quad").start(self)


try:
    from kivy.factory import Factory

    Factory.register("AnimatedCard", cls=AnimatedCard)
except Exception:
    pass

