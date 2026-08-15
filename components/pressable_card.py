from __future__ import annotations

from kivy.animation import Animation
from kivy.properties import NumericProperty

from core.fintech_widgets import GradientMDCard


class PressableCard(GradientMDCard):
    """Card that scales slightly on touch for action grids and hero actions."""

    press_scale = NumericProperty(0.96)
    press_duration = NumericProperty(0.08)
    release_duration = NumericProperty(0.12)

    def animate_in(self, *_args):
        """Pressable cards do not run their own entrance animation."""
        return

    def on_touch_down(self, touch):
        if not self.disabled and self.collide_point(*touch.pos):
            self._animate_pressed()
        return super().on_touch_down(touch)

    def on_touch_up(self, touch):
        if not self.disabled and self.collide_point(*touch.pos):
            self._animate_released()
        return super().on_touch_up(touch)

    def _animate_pressed(self) -> None:
        Animation.cancel_all(self, "scale_value")
        Animation(scale_value=float(self.press_scale or 0.96), duration=float(self.press_duration or 0.08), transition="out_quad").start(self)

    def _animate_released(self) -> None:
        Animation.cancel_all(self, "scale_value")
        Animation(scale_value=1.0, duration=float(self.release_duration or 0.12), transition="out_back").start(self)

    def pulse(self):
        self._animate_pressed()
        Animation(scale_value=1.0, duration=float(self.release_duration or 0.12), transition="out_back").start(self)


try:
    from kivy.factory import Factory

    Factory.register("PressableCard", cls=PressableCard)
except Exception:
    pass
