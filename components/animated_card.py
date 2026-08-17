from __future__ import annotations

from kivy.animation import Animation
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.properties import NumericProperty

from core.animation_helpers import AnimationManager
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
        AnimationManager.slide_up(
            self,
            distance=float(self.entrance_offset or 0),
            duration=float(self.entrance_duration or 0.45),
        )

    def animate_enter(self, *_args):
        self.animate_in(*_args)

    def pulse(self):
        Animation.cancel_all(self, "scale_value")
        Animation(scale_value=0.96, duration=0.08, transition="out_quad").start(self)
        Animation(scale_value=1.0, duration=0.14, transition="out_back").start(self)

    def press_animation(self):
        self.pulse()


try:
    from kivy.factory import Factory

    Factory.register("AnimatedCard", cls=AnimatedCard)
except Exception:
    pass
