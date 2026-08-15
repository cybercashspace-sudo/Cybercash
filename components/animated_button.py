from __future__ import annotations

from kivy.properties import NumericProperty
from kivymd.uix.button import MDRaisedButton

from animations.effects import AnimationManager


class AnimatedButton(MDRaisedButton):
    """Button with a subtle press animation."""

    press_scale = NumericProperty(0.97)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(on_press=self._animate_press)

    def _animate_press(self, *_args):
        AnimationManager.pulse(self, shrink=float(self.press_scale or 0.97), duration=0.14)


try:
    from kivy.factory import Factory

    Factory.register("AnimatedButton", cls=AnimatedButton)
except Exception:
    pass
